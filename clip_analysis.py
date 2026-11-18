"""Analyze captions or measured speech in bounded windows, including live snapshots."""

from collections import OrderedDict
import math
import os
import queue
import secrets
import threading
import time

from analyzer import (
    analyze_virality_and_cut_clips, extract_youtube_id, fetch_transcript_segments, get_video_metadata,
)
from api.clip_metadata import add_clip_metadata
from api.youtube_access import download_error_response, extract_youtube_info
from live_capture import capture_live_window
from source_uploads import SourceUploads
from video_engine import select_export_streams, stream_http_input_args, transcribe_audio_with_whisper


def validate_analysis(payload):
    mode = payload.get("analysis_mode", "auto")
    if mode not in ("auto","recent","range"):
        raise ValueError("Choose automatic scanning, recent live footage, or a time range.")
    try:
        start = float(payload.get("analysis_start",0))
        minutes = int(payload.get("analysis_minutes",10))
    except (TypeError,ValueError,OverflowError):
        raise ValueError("Enter a valid start time and scan length.") from None
    if not math.isfinite(start) or start < 0 or minutes not in (5,10,20,30):
        raise ValueError("Choose a scan length from 5 to 30 minutes and a valid start time.")
    return {**payload,"analysis_mode":mode,"analysis_start":start,"analysis_minutes":minutes}


def analysis_windows(duration, payload):
    seconds = payload["analysis_minutes"]*60
    if payload["analysis_mode"] == "range":
        start = payload["analysis_start"]
        if start >= duration:
            raise ValueError("The scan starts after the video ends.")
        return [(start,min(duration,start+seconds))]
    if payload["analysis_mode"] == "recent":
        return [(max(0,duration-seconds),duration)]
    if duration <= 1800:
        return [(0,duration)]
    # Sample across the full recording without downloading an hours-long audio file.
    length = 240
    return [(round(index*(duration-length)/5,2),round(index*(duration-length)/5+length,2))
            for index in range(6)]


def offset_speech(speech, offset):
    return [{**segment,"start":segment["start"]+offset,"end":segment["end"]+offset,
             "words":[{**word,"start":word["start"]+offset,"end":word["end"]+offset}
                      for word in segment.get("words",[])]} for segment in speech]


def analyze_source(payload, sources, report):
    payload = validate_analysis(payload)
    url, video_id = payload["url"], extract_youtube_id(payload["url"])
    if not video_id:
        raise ValueError("Please provide a valid YouTube video URL.")
    report("Loading video information",None)
    meta = get_video_metadata(video_id,url)
    live = bool(meta.get("is_live") or meta.get("live_status") == "is_live")
    transcript, upload_id = [], None
    if not live:
        report("Checking available captions",None)
        transcript = fetch_transcript_segments(video_id,url=url,video_title=meta.get("title",""))
    duration = float(meta.get("duration") or 0)
    source = "captions"
    if live or not transcript:
        report("Opening the video audio",None)
        info = extract_youtube_info(url,{"quiet":True,"no_warnings":True})
        if info.get("live_status") == "is_upcoming":
            raise ValueError("This stream has not started yet. Try again once it is broadcasting.")
        live = bool(info.get("is_live") or info.get("live_status") == "is_live")
        if live:
            if payload["analysis_mode"] == "range":
                raise ValueError("Use Recent live footage for an ongoing stream. Time ranges are available after the stream ends.")
            path, duration = capture_live_window(info,payload["analysis_minutes"]*60,report)
            try:
                upload_id = sources.adopt(path)
            finally:
                if os.path.exists(path):
                    os.remove(path)
            audio = sources.completed_path(upload_id)
            input_args = ["-protocol_whitelist","file,pipe"]
            windows = [(0,duration)]
        else:
            duration = float(info.get("duration") or duration)
            if not math.isfinite(duration) or duration <= 0:
                raise ValueError("Could not read this video's length. Try again after the stream finishes processing.")
            _,audio,_ = select_export_streams(info)
            input_args = stream_http_input_args(info,audio)
            windows = analysis_windows(duration,payload)
        source = "speech"
        # Keep each speech decode bounded. Absolute word times are restored exactly once.
        total = sum(end-start for start,end in windows)
        completed = 0.
        for start,end in windows:
            position = start
            while position < end:
                stop = min(position+240,end)
                report("Transcribing speech",round(100*completed/total))
                measured = transcribe_audio_with_whisper(url,position,stop,audio_stream_url=audio,
                                                        input_args=input_args)
                transcript.extend(offset_speech(measured,position))
                completed += stop-position
                position = stop
    else:
        duration = max(duration,max(float(item["end"]) for item in transcript))
        windows = analysis_windows(duration,payload) if payload["analysis_mode"] != "auto" else [(0,duration)]
    if not transcript:
        raise ValueError("No clear speech was detected in the scanned footage. Choose another time range.")
    transcript.sort(key=lambda cue: cue["start"])
    report("Finding complete clip endings",None)
    clips = []
    # Keep selection inside each scanned section so no untranscribed gaps become clips.
    for start,end in windows:
        section = [cue for cue in transcript if start <= cue["start"] < end and cue["end"] <= end+.01]
        clips.extend(analyze_virality_and_cut_clips(section,end,meta.get("title",""),
                     chapters=[] if live else meta.get("chapters",[]), ranges=[(start,end)]))
    clips.sort(key=lambda clip: clip["virality_score"],reverse=True)
    clips = clips[:5]
    for index,clip in enumerate(clips,1):
        clip["id"],clip["rank"] = f"clip_{index}",index
        clip["caption_source"] = source
    return {
        "success":True,"video":{
            "id":video_id,"url":url,"title":meta.get("title", "YouTube video"),
            "author":meta.get("author","Creator"),"thumbnail":meta.get("thumbnail"),
            "duration":duration,"duration_formatted":f"{int(duration)//60}:{int(duration)%60:02d}",
            "recommended_layout":"split","is_live":live,"upload_id":upload_id,
        },
        "clips":add_clip_metadata(clips,meta.get("title",""),meta.get("author",""),url),
        "transcript_available":True,"transcript_source":source,
        "analyzed_ranges":[{"start":start,"end":end} for start,end in windows],
        "message":("A replay window was saved for this live stream. Clip times refer to that saved window." if live else
                   "Speech was transcribed in sampled sections across the recording. Choose a time range to scan another section."
                   if len(windows)>1 else "Clips were selected from the scanned speech."),
    }


class AnalysisJobs:
    def __init__(self, sources=None, analyzer=analyze_source):
        self.sources = sources or SourceUploads()
        self.analyzer = analyzer
        self.jobs = OrderedDict()
        self.pending = queue.Queue(maxsize=3)
        self.lock = threading.Lock()
        threading.Thread(target=self._work,daemon=True).start()

    def submit(self, payload):
        with self.lock:
            now = time.monotonic()
            for token,job in list(self.jobs.items()):
                if job["state"] in ("complete","failed") and now-job["updated"] > 3600:
                    del self.jobs[token]
            if len(self.jobs) >= 16:
                raise queue.Full
            token = secrets.token_urlsafe(24)
            self.jobs[token] = {"id":token,"state":"queued","updated":now}
            try:
                self.pending.put_nowait((token,payload))
            except queue.Full:
                del self.jobs[token]
                raise
            return {"id":token,"state":"queued"}

    def snapshot(self, token):
        with self.lock:
            job = self.jobs.get(token)
            if job and job["state"] in ("complete","failed") and time.monotonic()-job["updated"] > 3600:
                del self.jobs[token]
                return None
            return {key:value for key,value in job.items() if key != "updated"} if job else None

    def _work(self):
        while True:
            token,payload = self.pending.get()
            def report(stage,percent):
                with self.lock:
                    self.jobs[token]["progress"] = {"stage":stage,"percent":percent}
            try:
                with self.lock:
                    self.jobs[token]["state"] = "analyzing"
                result = self.analyzer(payload,self.sources,report)
                with self.lock:
                    self.jobs[token].update(state="complete",result=result,updated=time.monotonic())
            except Exception as error:
                _,code,message = download_error_response(error)
                if isinstance(error,ValueError):
                    code,message = "ANALYSIS_FAILED",str(error)
                with self.lock:
                    self.jobs[token].update(state="failed",error=message,code=code,updated=time.monotonic())
            finally:
                self.pending.task_done()
