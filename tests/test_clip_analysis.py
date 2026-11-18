import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.request
from unittest.mock import patch

from clip_analysis import AnalysisJobs, analysis_windows, analyze_source, offset_speech, validate_analysis
from live_capture import ReplayTooShort, freeze_hls
from source_uploads import SourceUploads


URL = "https://www.youtube.com/watch?v=abcdefghijk"


def speech():
    return [
        {"start":0,"end":8,"text":"How does the system work?",
         "words":[{"word":"How","start":0,"end":1}]},
        {"start":8,"end":40,"text":"Start by checking the input before every run."},
        {"start":40,"end":65,"text":"The checks keep the system stable and reliable."},
        {"start":65,"end":78,"text":"That is why the output stays consistent."},
        {"start":80,"end":88,"text":"Next question, how do you change the setup?"},
        {"start":88,"end":110,"text":"You can change the input from the control panel."},
    ]


class ClipAnalysisTests(unittest.TestCase):
    def test_conversational_speech_can_close_on_a_measured_sentence_pause(self):
        from api.clip_boundaries import select_short_clip_windows
        cues = [
            {"start":0,"end":15,"text":"A good microphone makes voices easier to understand."},
            {"start":16,"end":55,"text":"Position the microphone closer and reduce background noise."},
            {"start":56,"end":74,"text":"The voice sounds clear after that adjustment.",
             "words":[{"word":word,"start":56+index*2,"end":58+index*2}
                      for index,word in enumerate("The voice sounds clear after that adjustment.".split())]},
            {"start":77,"end":155,"text":"A different player joins the next match."},
        ]
        windows = select_short_clip_windows(cues,155)
        self.assertTrue(windows)
        self.assertTrue(any(end < 77 for _,end,_ in windows))

    def test_no_captions_transcribes_selected_range_with_absolute_word_times(self):
        payload = validate_analysis({"url":URL,"analysis_mode":"range","analysis_start":3600,"analysis_minutes":5})
        info = {"duration":7200}
        with patch("clip_analysis.get_video_metadata",return_value={"duration":7200,"title":"System"}), patch(
                "clip_analysis.fetch_transcript_segments",return_value=[]), patch(
                "clip_analysis.extract_youtube_info",return_value=info), patch(
                "clip_analysis.select_export_streams",return_value=("video","audio",True)), patch(
                "clip_analysis.transcribe_audio_with_whisper",side_effect=[speech(),[]]) as transcribe:
            result = analyze_source(payload,None,lambda *args: None)
        self.assertEqual(result["transcript_source"],"speech")
        self.assertTrue(result["clips"])
        self.assertTrue(all(3600 <= clip["start"] < clip["end"] <= 3900 for clip in result["clips"]))
        self.assertEqual(transcribe.call_args_list[0].args,(URL,3600,3840))
        shifted = offset_speech(speech(),3600)
        self.assertEqual(shifted[0]["words"][0]["start"],3600)
        self.assertEqual(speech()[0]["words"][0]["start"],0)

    def test_long_recordings_sample_the_whole_duration_and_respect_requested_range(self):
        payload = validate_analysis({"url":URL})
        windows = analysis_windows(16*3600,payload)
        self.assertEqual(len(windows),6)
        self.assertEqual(windows[0][0],0)
        self.assertEqual(windows[-1][1],16*3600)
        self.assertEqual(sum(end-start for start,end in windows),24*60)
        selected = validate_analysis({"url":URL,"analysis_mode":"range","analysis_start":15*3600,"analysis_minutes":30})
        self.assertEqual(analysis_windows(16*3600,selected),[(15*3600,15*3600+1800)])
        with self.assertRaises(ValueError):
            analysis_windows(100,validate_analysis({"url":URL,"analysis_mode":"range","analysis_start":120}))

    def test_partial_punctuation_does_not_disable_measured_pause_selection(self):
        from api.clip_boundaries import select_short_clip_windows
        cues = [
            {"start":0,"end":8,"text":"we won the first round.",
             "words":[{"word":"round","end":4}]},
            {"start":6,"end":40,"text":"okay lets set up for a retake"},
            {"start":40,"end":78,"text":"they held the site and won the round",
             "words":[{"word":"round","end":73}]},
            {"start":76,"end":90,"text":"all right lets check the score"},
        ]
        self.assertEqual(select_short_clip_windows(cues,90)[0][:2],(6,73.18))

    def test_existing_captions_skip_speech_download(self):
        with patch("clip_analysis.get_video_metadata",return_value={"duration":110,"title":"System"}), patch(
                "clip_analysis.fetch_transcript_segments",return_value=speech()), patch(
                "clip_analysis.extract_youtube_info") as extract:
            result = analyze_source({"url":URL},None,lambda *args: None)
        self.assertTrue(result["clips"])
        self.assertEqual(result["transcript_source"],"captions")
        extract.assert_not_called()

    def test_live_capture_is_registered_and_transcribed_as_a_local_source(self):
        with tempfile.TemporaryDirectory() as directory:
            sources = SourceUploads(directory)
            path = Path(directory)/"capture.mp4"
            path.write_bytes(b"captured video")
            with patch("clip_analysis.get_video_metadata",return_value={"is_live":True,"duration":None,"title":"Live"}), patch(
                    "clip_analysis.fetch_transcript_segments") as captions, patch(
                    "clip_analysis.extract_youtube_info",return_value={"is_live":True}), patch(
                    "clip_analysis.capture_live_window",return_value=(str(path),110)), patch(
                    "clip_analysis.transcribe_audio_with_whisper",return_value=speech()) as transcribe:
                result = analyze_source({"url":URL},sources,lambda *args: None)
            captions.assert_not_called()
            token = result["video"]["upload_id"]
            self.assertEqual(Path(sources.completed_path(token)).read_bytes(),b"captured video")
            self.assertEqual(transcribe.call_args.kwargs["audio_stream_url"],sources.completed_path(token))
            self.assertTrue(result["video"]["is_live"])
            self.assertTrue(result["clips"])

    def test_analysis_job_returns_immediately_and_reports_results(self):
        running,finish = threading.Event(),threading.Event()
        def analyze(payload,sources,report):
            report("Transcribing speech",10)
            running.set()
            finish.wait(3)
            return {"success":True,"clips":[]}
        jobs = AnalysisJobs(analyzer=analyze)
        job = jobs.submit({"url":URL})
        try:
            self.assertTrue(running.wait(2))
            self.assertEqual(jobs.snapshot(job["id"])["progress"]["percent"],10)
        finally:
            finish.set()
        jobs.pending.join()
        self.assertEqual(jobs.snapshot(job["id"])["result"],{"success":True,"clips":[]})


class LivePlaylistTests(unittest.TestCase):
    def test_freezes_tail_with_original_sequence_keys_and_absolute_media_urls(self):
        playlist = ('#EXTM3U\n#EXT-X-TARGETDURATION:10\n#EXT-X-MEDIA-SEQUENCE:100\n'
                    '#EXT-X-KEY:METHOD=AES-128,URI="key.bin"\n')
        playlist += "".join(f"#EXTINF:10,\nseg-{i}.ts\n" for i in range(20))
        frozen,duration = freeze_hls(playlist,"https://example.test/media/index.m3u8",80)
        self.assertEqual(duration,80)
        self.assertIn("#EXT-X-MEDIA-SEQUENCE:112",frozen)
        self.assertIn('URI="https://example.test/media/key.bin"',frozen)
        self.assertNotIn("/seg-11.ts",frozen)
        self.assertIn("https://example.test/media/seg-12.ts",frozen)
        self.assertTrue(frozen.endswith("#EXT-X-ENDLIST\n"))

    def test_short_replay_selects_live_recording_and_rejects_local_segment_addresses(self):
        with self.assertRaises(ReplayTooShort):
            freeze_hls("#EXTM3U\n#EXTINF:10,\nsegment.ts\n","https://example.test/live",300)
        with self.assertRaisesRegex(ValueError,"unsupported media"):
            freeze_hls("#EXTM3U\n#EXTINF:100,\nfile:///secret\n","https://example.test/live",100)

    def test_audio_and_video_snapshots_use_the_same_wall_clock_end(self):
        from live_capture import playlist_times
        text = "#EXTM3U\n#EXT-X-TARGETDURATION:10\n#EXT-X-PROGRAM-DATE-TIME:2026-11-18T12:00:00Z\n"
        text += "".join(f"#EXTINF:10,\nsegment-{index}.ts\n" for index in range(20))
        until = playlist_times(text)[1]-20
        frozen,duration = freeze_hls(text,"https://example.test/live",80,until)
        start,end = playlist_times(frozen)
        self.assertEqual(end,until)
        self.assertEqual(end-start,duration)
        self.assertNotIn("/segment-18.ts",frozen)


class ClipAnalysisHTTPTests(unittest.TestCase):
    def test_analysis_runs_in_background_and_live_preview_accepts_byte_ranges(self):
        from server import GoddAIRequestHandler, ThreadedHTTPServer
        started,finish = threading.Event(),threading.Event()
        def analyze(payload,sources,report):
            report("Transcribing speech",20)
            started.set()
            finish.wait(3)
            return {"success":True,"clips":[]}
        with tempfile.TemporaryDirectory() as directory:
            sources = SourceUploads(directory)
            media = Path(directory)/"window.mp4"
            media.write_bytes(b"0123456789")
            source = sources.adopt(str(media))
            jobs = AnalysisJobs(sources,analyzer=analyze)
            with ThreadedHTTPServer(("127.0.0.1",0),GoddAIRequestHandler) as server, patch(
                    "server.ANALYSIS_JOBS",jobs), patch("server.SOURCE_UPLOADS",sources):
                threading.Thread(target=server.serve_forever,daemon=True).start()
                root = f"http://127.0.0.1:{server.server_port}"
                try:
                    request = urllib.request.Request(root+"/api/analyses",json.dumps({"url":URL}).encode(),
                                                     {"Content-Type":"application/json"})
                    with urllib.request.urlopen(request) as response:
                        self.assertEqual(response.status,202)
                        job = json.load(response)
                    self.assertTrue(started.wait(2))
                    with urllib.request.urlopen(root+"/api/analyses/"+job["id"]) as response:
                        self.assertEqual(json.load(response)["progress"]["percent"],20)
                    request = urllib.request.Request(root+"/api/source-previews/"+source,headers={"Range":"bytes=3-5"})
                    with urllib.request.urlopen(request) as response:
                        self.assertEqual(response.status,206)
                        self.assertEqual(response.headers["Content-Range"],"bytes 3-5/10")
                        self.assertEqual(response.read(),b"345")
                    with urllib.request.urlopen(root+"/") as response:
                        self.assertIn('id="analysisMode"',response.read().decode())
                    with urllib.request.urlopen(root+"/app.js") as response:
                        self.assertIn("'/api/analyses'",response.read().decode())
                finally:
                    finish.set()
                    server.shutdown()


if __name__ == "__main__":
    unittest.main()
