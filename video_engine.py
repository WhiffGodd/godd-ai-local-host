import os
import re
import subprocess
import tempfile
import shutil
import math
import threading
import json
import gc
from caption_styles import generate_ass
from api.youtube_access import youtube_options, extract_youtube_info

_WHISPER_LOCK = threading.Lock()

try:
    import imageio_ffmpeg
except ImportError:
    imageio_ffmpeg = None

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

try:
    from faster_whisper import WhisperModel
    _whisper_model = None
    WHISPER_AVAILABLE = True
except ImportError:
    WhisperModel = None
    _whisper_model = None
    WHISPER_AVAILABLE = False


def _get_whisper_model():
    """Lazy-load the configured Whisper model (cached globally for reuse across requests)."""
    global _whisper_model
    if _whisper_model is None and WHISPER_AVAILABLE:
        print("[Whisper] Loading faster-whisper speech model...")
        _whisper_model = WhisperModel(os.environ.get("WHISPER_MODEL", "small"), device="cpu", compute_type="int8", cpu_threads=int(os.environ.get("WHISPER_CPU_THREADS", "4")))
        print("[Whisper] Model loaded.")
    return _whisper_model


def transcribe_audio_with_whisper(video_url: str, start_sec: float, end_sec: float,
                                  audio_stream_url: str = None) -> list:
    """Transcribe the selected export audio; return clip-relative speech timings."""
    if not WHISPER_AVAILABLE:
        raise RuntimeError("Automatic subtitles require faster-whisper. Install requirements.txt or select subtitles Off.")
    if not audio_stream_url:
        if not yt_dlp:
            raise RuntimeError("yt-dlp is not installed")
        info = extract_youtube_info(video_url, {'quiet': True, 'no_warnings': True})
        _, audio_stream_url, _ = select_export_streams(info)
    with tempfile.TemporaryDirectory(prefix="godd_ai_speech_") as tmp_dir:
        wav_path = os.path.join(tmp_dir, "speech.wav")
        cmd = [FFMPEG_PATH, "-y", "-ss", str(start_sec), "-i", audio_stream_url,
               "-t", str(end_sec - start_sec), "-map", "0:a:0", "-vn",
               "-af", "aresample=async=1:first_pts=0", "-ar", "16000", "-ac", "1", wav_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=max(120, (end_sec - start_sec) * 4))
        if result.returncode:
            raise RuntimeError(f"Could not extract speech for subtitles: {result.stderr[-500:]}")
        # Serialize model use and loading across HTTP request threads.
        with _WHISPER_LOCK:
            model = _get_whisper_model()
            segments, _ = model.transcribe(wav_path, beam_size=5, temperature=0.0,
                                            task="transcribe", language=os.environ.get("WHISPER_LANGUAGE") or None,
                                            vad_filter=False, word_timestamps=True,
                                            hallucination_silence_threshold=2.0,
                                            condition_on_previous_text=False)
            recognized = [{"text": seg.text.strip(), "start": float(seg.start),
                     "end": float(seg.end), "duration": float(seg.end - seg.start),
                     "words": [{"word": w.word.strip(), "start": float(w.start),
                                "end": float(w.end)} for w in (seg.words or [])]}
                    for seg in segments if seg.text.strip()]
            if os.environ.get("RELEASE_WHISPER_MODEL") == "1":
                global _whisper_model
                _whisper_model = None
                del model
                gc.collect()
            return recognized


def speech_words_for_clip(speech, duration):
    """Keep recognized text within clip bounds, using neighboring timing anchors.

    Whisper can emit zero-length tokens; retain them until the next measured
    word boundary rather than losing spoken text or inventing a fixed duration.
    """
    result = []
    for segment in speech:
        words = segment.get("words") or []
        for index, word in enumerate(words):
            start = max(0.0, float(word.get("start", 0)))
            end = min(duration, float(word.get("end", start)))
            if end <= start:
                end = min(duration, next((float(other["start"]) for other in words[index + 1:]
                                           if float(other["start"]) > start), float(segment.get("end", start))))
            if word.get("word") and start < duration and end > start:
                result.append({"word": word["word"], "start": start, "end": end})
    return result


def select_export_streams(info):
    """Select one video and one audio rendition, preferring original speech."""
    formats = info.get("formats") or info.get("requested_formats") or [info]
    videos = [f for f in formats if f.get("url") and f.get("vcodec") not in (None, "none", "")
              and (f.get("height") or 0) <= 1080]
    if not videos:
        raise RuntimeError("Could not find playable video stream URL")
    video = max(videos, key=lambda f: (f.get("height") or 0, f.get("tbr") or 0))
    audios = [f for f in formats if f.get("url") and f.get("acodec") not in (None, "none", "")]
    def audio_rank(f):
        note = str(f.get("format_note", "")).lower()
        return ("original" in note, f.get("language_preference") or 0,
                f.get("vcodec") in (None, "none", ""), f.get("abr") or 0)
    audio = max(audios, key=audio_rank) if audios else None
    if audio is None:
        raise RuntimeError("No audio track found for this video")
    return video["url"], audio["url"], video["url"] != audio["url"]


def stream_http_input_args(info, stream_url):
    """Keep the extractor's playback headers when FFmpeg fetches its URLs."""
    selected = next((fmt for fmt in info.get("formats", []) if fmt.get("url") == stream_url), info)
    headers = selected.get("http_headers") or info.get("http_headers") or {}
    # Headers come from the extractor, not the web request payload. Remove line
    # breaks so a header value cannot introduce another FFmpeg HTTP header.
    values = [(str(key), str(value)) for key, value in headers.items()
              if "\r" not in str(key) + str(value) and "\n" not in str(key) + str(value)]
    return ["-headers", "".join(f"{key}: {value}\r\n" for key, value in values)] if values else []


# Locate FFmpeg binary (System PATH -> imageio_ffmpeg -> fallback)
FFMPEG_PATH = shutil.which("ffmpeg")
if not FFMPEG_PATH and imageio_ffmpeg:
    try:
        FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        FFMPEG_PATH = "ffmpeg"
if not FFMPEG_PATH:
    FFMPEG_PATH = "ffmpeg"

_DETECTED_ENCODER = None

def get_video_encoder_flags():
    """Detect whether NVIDIA NVENC GPU acceleration is available on this system."""
    global _DETECTED_ENCODER
    if _DETECTED_ENCODER is not None:
        return _DETECTED_ENCODER
        
    try:
        probe = subprocess.run(
            [FFMPEG_PATH, "-f", "lavfi", "-i", "nullsrc=s=256x256,format=yuv420p", "-c:v", "h264_nvenc", "-t", "0.05", "-f", "null", "-"],
            capture_output=True, timeout=3
        )
        if probe.returncode == 0:
            print("[VideoEngine] 🚀 NVIDIA NVENC GPU Hardware Acceleration DETECTED & ACTIVE (1080p 12M preset)!")
            _DETECTED_ENCODER = ["-c:v", "h264_nvenc", "-preset", "p6", "-tune", "hq", "-b:v", "12M", "-maxrate", "16M", "-bufsize", "24M"]
            return _DETECTED_ENCODER
    except Exception:
        pass
        
    print("[VideoEngine] Using CPU libx264 encoder (CRF 18 visually lossless).")
    _DETECTED_ENCODER = ["-c:v", "libx264", "-preset", os.environ.get("ENCODER_PRESET", "fast"), "-crf", "20", "-threads", os.environ.get("FFMPEG_THREADS", "2")]
    return _DETECTED_ENCODER

def clean_streamer_text(text: str) -> str:
    """Strip HTML entities, speaker tags (<<, >>), and bracketed sounds."""
    if not text:
        return ""
    cleaned = re.sub(r'&(?:lt|gt|amp|quot|apos);?', ' ', str(text))
    cleaned = re.sub(r'[«»<>]+', ' ', cleaned)
    cleaned = re.sub(r'\[.*?\]|\(.*?\)|♪+', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

def generate_srt(subtitles: list, clip_start: float = 0.0, video_subtitles: list = None,
                 clip_duration: float = None) -> str:
    """Convert absolute source timestamps to bounded, clip-relative SRT cues."""
    cues = []
    for item in (video_subtitles or subtitles or []):
        text = clean_streamer_text(item.get("text", item.get("word", "")))
        try:
            start = float(item.get("start", 0)) - clip_start
            end = float(item.get("end", float(item.get("start", 0)) + float(item.get("duration", 0)))) - clip_start
        except (ValueError, TypeError):
            continue
        if not text or not math.isfinite(start) or not math.isfinite(end) or end <= 0:
            continue
        start = max(0.0, start)
        if clip_duration is not None:
            end = min(end, clip_duration)
        if end > start:
            cues.append({"text": text, "start": start, "end": end})
    cues.sort(key=lambda c: c["start"])
    if not video_subtitles:
        groups, group = [], []
        for i, cue in enumerate(cues):
            group.append(cue)
            gap = i + 1 < len(cues) and cues[i + 1]["start"] - cue["end"] >= 0.38
            if len(group) >= 4 or cue["text"].endswith((".", "!", "?")) or gap or i == len(cues) - 1:
                groups.append({"text": " ".join(c["text"] for c in group),
                               "start": group[0]["start"], "end": max(c["end"] for c in group)})
                group = []
        cues = groups
    lines = []
    for i, cue in enumerate(cues):
        end = min(cue["end"], cues[i + 1]["start"]) if i + 1 < len(cues) else cue["end"]
        if round(end * 1000) <= round(cue["start"] * 1000):
            continue
        lines.extend([str(len(lines) // 4 + 1),
                      f"{format_srt_timestamp(cue['start'])} --> {format_srt_timestamp(end)}",
                      cue["text"], ""])
    return "\n".join(lines)


def format_srt_timestamp(seconds: float) -> str:
    millis = max(0, round(seconds * 1000))
    secs, millis = divmod(millis, 1000)
    mins, secs = divmod(secs, 60)
    hrs, mins = divmod(mins, 60)
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"

FACE_MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "face_detection_yunet.onnx")

def detect_facecam_in_stream(stream_url: str, timestamp: float = 10.0) -> dict:
    """
    Sample 1 frame from the video stream using FFmpeg image2pipe and detect if a streamer
    facecam exists using OpenCV's fast YuNet face detector.
    Returns: {"has_face": True/False, "x": int, "y": int, "w": int, "h": int, "orig_w": int, "orig_h": int}
    """
    if not stream_url or not os.path.exists(FACE_MODEL_PATH):
        return {"has_face": False}
    try:
        import cv2
        import numpy as np

        ffmpeg_bin = FFMPEG_PATH or "ffmpeg"
        cmd = [
            ffmpeg_bin, "-y",
            "-ss", str(max(0.0, timestamp)),
            "-i", stream_url,
            "-vframes", "1",
            "-f", "image2pipe",
            "-vcodec", "png",
            "-"
        ]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        out, _ = p.communicate(timeout=6)
        if not out or len(out) < 1000:
            return {"has_face": False}

        arr = np.frombuffer(out, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return {"has_face": False}

        h, w = img.shape[:2]
        detector = cv2.FaceDetectorYN.create(FACE_MODEL_PATH, "", (w, h), score_threshold=0.55)
        _, faces = detector.detect(img)
        if faces is not None and len(faces) > 0:
            best = max(faces, key=lambda f: float(f[-1]))
            fx, fy, fw, fh = [int(v) for v in best[:4]]
            score = float(best[-1])
            print(f"[FaceCam] Streamer face detected at x={fx}, y={fy}, w={fw}, h={fh} (confidence: {score:.2f})")
            return {
                "has_face": True,
                "x": fx, "y": fy, "w": fw, "h": fh,
                "orig_w": w, "orig_h": h,
                "score": score
            }
        print("[FaceCam] No streamer facecam detected in video frame.")
        return {"has_face": False, "orig_w": w, "orig_h": h}
    except Exception as e:
        print(f"[FaceCam] Detection notice: {e}")
        return {"has_face": False}

def download_and_clip_video(
    video_url: str,
    start_time: float,
    duration: float,
    layout: str = "split",
    subtitles: list = None,
    output_path: str = None,
    subtitle_style: str = "source",
    video_subtitles: list = None,
    caption_source: str = "auto",
    local_source_path: str = None
) -> str:
    """
    Download and render a Full HD 1080p (1080x1920) 9:16 short using FFmpeg.
    Layouts:
    - 'split': If streamer facecam is detected -> upper facecam zoomed & centered (1080x780) + full 16:9 gameplay below.
               If NO facecam is detected -> automatically uses unified single-section 1080p (no duplicate sections).
    - 'crop': Smart center crop to 1080x1920 Full HD
    - 'blur': Blurred ambient background (1080x1920) with crisp centered 16:9 video
    - 'fit': Fitted 16:9 on 1080x1920 canvas with clean letterbox
    """
    if not math.isfinite(start_time) or not math.isfinite(duration) or start_time < 0 or duration <= 0:
        raise ValueError("Clip start must be non-negative and duration must be positive")

    owns_output = output_path is None
    if not output_path:
        tmp_dir = os.path.join(tempfile.gettempdir(), "godd_ai_clips")
        os.makedirs(tmp_dir, exist_ok=True)
        fd, output_path = tempfile.mkstemp(prefix="godd_ai_", suffix=".mp4", dir=tmp_dir)
        os.close(fd)

    if not yt_dlp:
        raise RuntimeError("yt-dlp is not installed")

    srt_temp_file = None
    try:
        if local_source_path:
            # This path is resolved from an upload token by the server, never
            # accepted as a filesystem path in a visitor's request.
            info = {"formats": [{"url": local_source_path, "vcodec": "local",
                                 "acodec": "local", "height": 1080}]}
        else:
            info = extract_youtube_info(video_url, {
                'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/best',
                'quiet': True, 'no_warnings': True,
            })
        target_stream, selected_audio, separate_audio = select_export_streams(info)
        srt_filter = ""
        is_none_style = str(subtitle_style).lower() in ("none", "off", "disable", "disabled", "false")
        if not is_none_style and caption_source != "auto":
            if not video_subtitles and not subtitles:
                speech = transcribe_audio_with_whisper(video_url, start_time, start_time + duration,
                                                       audio_stream_url=selected_audio)
                # Whisper times are relative to the extracted clip. Convert once.
                subtitles = [{"word": w["word"], "start": w["start"] + start_time,
                              "end": w["end"] + start_time}
                             for seg in speech for w in (seg.get("words") or [
                                 {"word": seg["text"], "start": seg["start"], "end": seg["end"]}])]
            srt_content = generate_srt(subtitles, start_time,
                                       video_subtitles if subtitle_style == "source" or not subtitles else None, duration)
            if srt_content.strip():
                fd, srt_temp_file = tempfile.mkstemp(prefix="godd_ai_subs_", suffix=".ass")
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(generate_ass(srt_content, subtitle_style, subtitles, start_time))
                esc_srt = srt_temp_file.replace('\\', '/').replace(':', '\\:').replace("'", "'\\''")
                srt_filter = f",subtitles='{esc_srt}'"

        # Check whether streamer facecam exists in this video
        face_info = {"has_face": False}
        if layout == "split":
            face_info = detect_facecam_in_stream(target_stream, start_time + 1.5)

        # Full HD 1080x1920 Filter graph based on layout & facecam detection
        if layout == "split":
            if face_info.get("has_face"):
                fx = face_info["x"]
                fy = face_info["y"]
                fw = face_info["w"]
                fh = face_info["h"]
                orig_w = face_info.get("orig_w", 1920)
                orig_h = face_info.get("orig_h", 1080)

                # Head and shoulders framing: facecam fills the 1080x780 upper section prominently
                cam_crop_h = int(fh * 2.6)
                cam_crop_w = int(cam_crop_h * (1080.0 / 780.0))
                cam_crop_w = max(cam_crop_w, int(orig_w * 0.20))
                cam_crop_w = min(cam_crop_w, int(orig_w * 0.45))
                cam_crop_h = int(cam_crop_w * (780.0 / 1080.0))

                crop_x = max(0, min(orig_w - cam_crop_w, int(fx + fw/2 - cam_crop_w/2)))
                crop_y = max(0, min(orig_h - cam_crop_h, int(fy + fh/2 - cam_crop_h/2)))

                cam_filter = f"crop={cam_crop_w}:{cam_crop_h}:{crop_x}:{crop_y},scale=1080:780"
                print(f"[VideoEngine] Framing 1080p streamer facecam: {cam_filter}")

                filter_complex = (
                    "[0:v]split=2[cam_src][game_src];"
                    f"[cam_src]{cam_filter}[cam];"
                    "[game_src]scale=1080:608[game];"
                    f"color=c=#0B0C10:s=1080x1920:d={duration}[bg];"
                    "[bg][cam]overlay=0:0:shortest=1[bg_cam];"
                    f"[bg_cam][game]overlay=0:788:shortest=1{srt_filter}[outv]"
                )
            else:
                # Unified single-section 1080p 9:16 short
                print("[VideoEngine] No streamer facecam found — rendering unified single-section 1080p short.")
                filter_complex = (
                    "[0:v]split=2[bg][fg];"
                    "[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5[bg_blurred];"
                    "[fg]scale=1080:608[fg_scaled];"
                    f"[bg_blurred][fg_scaled]overlay=0:(1920-608)/2{srt_filter}[outv]"
                )
        elif layout == "blur":
            filter_complex = (
                "[0:v]split=2[bg][fg];"
                "[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5[bg_blurred];"
                "[fg]scale=1080:608[fg_scaled];"
                f"[bg_blurred][fg_scaled]overlay=0:(1920-608)/2{srt_filter}[outv]"
            )
        elif layout == "fit":
            filter_complex = f"scale=1080:-1,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black{srt_filter}[outv]"
        else: # Default: 'crop'
            filter_complex = f"crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920:flags=lanczos{srt_filter}[outv]"

        encoder_flags = get_video_encoder_flags()
        # Accurate seeks on both inputs share the same clip origin. Resample against
        # timestamps to correct drift and pad a late-starting audio stream.
        source_protocols = ["-protocol_whitelist", "file,pipe"] if local_source_path else []
        cmd = [FFMPEG_PATH, "-y", "-filter_complex_threads", os.environ.get("FFMPEG_THREADS", "2"), "-threads", os.environ.get("FFMPEG_THREADS", "2"), "-ss", str(start_time), *source_protocols, *stream_http_input_args(info, target_stream), "-i", target_stream]
        if separate_audio:
            cmd += ["-ss", str(start_time), *stream_http_input_args(info, selected_audio), "-i", selected_audio]
        cmd += ["-t", str(duration), "-filter_complex", filter_complex,
                "-map", "[outv]", "-map", "1:a:0" if separate_audio else "0:a:0",
                "-af", "aresample=async=1:first_pts=0,apad",
                *encoder_flags, "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                "-ac", "2", "-sn", "-dn", "-pix_fmt", "yuv420p",
                "-movflags", "+faststart", output_path]

        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=max(120, duration * 8))
        if result.returncode != 0:
            print(f"[FFmpeg] Error: {result.stderr}")
            raise RuntimeError(f"FFmpeg render failed: {result.stderr[:200]}")

        if not is_none_style and caption_source == "auto":
            speech = transcribe_audio_with_whisper(video_url, 0.0, duration,
                                                   audio_stream_url=output_path)
            measured_words = speech_words_for_clip(speech, duration)
            srt_content = generate_srt(measured_words, 0.0, clip_duration=duration)
            if srt_content.strip():
                fd, srt_temp_file = tempfile.mkstemp(prefix="godd_ai_aligned_", suffix=".ass")
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(generate_ass(srt_content, subtitle_style, measured_words, 0.0))
                esc_srt = srt_temp_file.replace('\\', '/').replace(':', '\\:').replace("'", "'\\''")
                fd, captioned_path = tempfile.mkstemp(prefix="godd_ai_captioned_", suffix=".mp4")
                os.close(fd)
                try:
                    burn = [FFMPEG_PATH, "-y", "-i", output_path,
                            "-vf", f"subtitles='{esc_srt}'", "-map", "0:v:0", "-map", "0:a:0",
                            *encoder_flags, "-c:a", "copy", "-pix_fmt", "yuv420p",
                            "-movflags", "+faststart", captioned_path]
                    encoded = subprocess.run(burn, capture_output=True, text=True, timeout=max(120, duration * 3))
                    if encoded.returncode:
                        raise RuntimeError(f"Caption rendering failed: {encoded.stderr[-500:]}")
                    shutil.move(captioned_path, output_path)
                finally:
                    if os.path.exists(captioned_path):
                        os.remove(captioned_path)
            # Sidecar timings are clip-relative and can update the site preview
            # and SRT export without another transcription or a guessed offset.
            with open(output_path + ".captions.json", "w", encoding="utf-8") as f:
                json.dump({"words": measured_words, "segments": speech,
                           "timing_origin": "clip", "measured_from": "rendered_audio"}, f, ensure_ascii=False)
            with open(output_path + ".srt", "w", encoding="utf-8") as f:
                f.write(srt_content)

        return output_path

    except Exception as e:
        if owns_output:
            for suffix in ("", ".captions.json", ".srt"):
                try:
                    os.remove(output_path + suffix)
                except OSError:
                    pass
        print(f"[VideoEngine] Error rendering video: {e}")
        raise

    finally:
        if srt_temp_file and os.path.exists(srt_temp_file):
            os.remove(srt_temp_file)
