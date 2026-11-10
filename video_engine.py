import os
import subprocess
import tempfile
import json
import shutil

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
    """Lazy-load Whisper tiny model (cached globally for reuse across requests)."""
    global _whisper_model
    if _whisper_model is None and WHISPER_AVAILABLE:
        print("[Whisper] Loading faster-whisper tiny model...")
        _whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
        print("[Whisper] Model loaded.")
    return _whisper_model


def transcribe_audio_with_whisper(video_url: str, start_sec: float, end_sec: float) -> list:
    """
    Download only the audio track for the given segment and transcribe it with
    faster-whisper (tiny model, CPU int8 — fast and low-RAM).

    Returns a list of dicts: [{text, start, duration, end}, ...]
    relative to 0.0 (not to video absolute time — caller adds offset).
    """
    if not WHISPER_AVAILABLE:
        print("[Whisper] faster-whisper not available, skipping.")
        return []
    if not yt_dlp:
        print("[Whisper] yt-dlp not available, skipping.")
        return []

    duration_sec = max(1.0, end_sec - start_sec)
    tmp_dir = os.path.join(tempfile.gettempdir(), "godd_ai_audio")
    os.makedirs(tmp_dir, exist_ok=True)
    wav_path = os.path.join(tmp_dir, f"seg_{int(start_sec)}_{int(end_sec)}.wav")

    try:
        # 1. Get audio-only stream URL via yt-dlp (no video download)
        ydl_opts = {
            'format': 'bestaudio[ext=m4a]/bestaudio/best',
            'extractor_args': {'youtube': {'player_client': ['android', 'ios', 'mweb']}},
            'quiet': True,
            'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            audio_url = info.get("url")
            if not audio_url and "formats" in info:
                # Pick best audio-only format
                for fmt in reversed(info["formats"]):
                    if fmt.get("acodec") != "none" and fmt.get("vcodec") in (None, "none", ""):
                        audio_url = fmt.get("url")
                        break
                if not audio_url:
                    # Fallback: any stream
                    for fmt in reversed(info["formats"]):
                        if fmt.get("url"):
                            audio_url = fmt["url"]
                            break

        if not audio_url:
            print("[Whisper] Could not obtain audio stream URL.")
            return []

        # 2. Download only the segment's audio as 16kHz mono WAV
        # Apply aggressive vocal-frequency boost: highpass 100Hz, boost 1800Hz presence
        # This emphasizes human voice (streamer mic) and cuts low-frequency game rumble
        cmd = [
            FFMPEG_PATH, "-y",
            "-ss", str(start_sec),
            "-i", audio_url,
            "-t", str(duration_sec),
            "-vn",                                        # no video
            "-af", (
                "highpass=f=100,"                         # cut bass/rumble below 100Hz
                "lowpass=f=8000,"                         # cut harsh highs above 8kHz
                "equalizer=f=1800:width_type=h:width=1200:g=5,"  # boost voice presence
                "equalizer=f=300:width_type=h:width=200:g=-4,"   # cut muddy low-mids
                "acompressor=threshold=-20dB:ratio=3:attack=5:release=100,"  # level streamer voice
                "volume=2.0"                              # extra gain for quiet mics
            ),
            "-ar", "16000",   # 16kHz required by Whisper
            "-ac", "1",       # mono
            "-f", "wav",
            wav_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)
        if result.returncode != 0:
            print(f"[Whisper] FFmpeg audio extraction failed: {result.stderr[:300]}")
            return []

        if not os.path.exists(wav_path) or os.path.getsize(wav_path) < 1000:
            print("[Whisper] WAV file too small or missing, skipping.")
            return []

        # 3. Transcribe with faster-whisper
        model = _get_whisper_model()
        if not model:
            return []

        # Try Hindi first (streamer Hinglish), fall back to multilingual auto-detect
        segments_out = []
        for lang in ["hi", None]:
            try:
                kwargs = {"beam_size": 1, "temperature": 0.0, "vad_filter": True}
                if lang:
                    kwargs["language"] = lang
                seg_gen, info_obj = model.transcribe(wav_path, **kwargs)
                raw_segments = list(seg_gen)

                if not raw_segments:
                    continue

                for seg in raw_segments:
                    text = (seg.text or "").strip()
                    if not text or text in ("[BLANK_AUDIO]", "[SILENCE]", "(Music)", "[Music]"):
                        continue
                    # Skip very short noise bursts
                    if len(text) < 3:
                        continue
                    segments_out.append({
                        "text": text,
                        "start": round(float(seg.start), 2),
                        "duration": round(float(seg.end) - float(seg.start), 2),
                        "end": round(float(seg.end), 2)
                    })

                if segments_out:
                    print(f"[Whisper] Transcribed {len(segments_out)} segments (lang={lang or 'auto'}).")
                    break
            except Exception as e:
                print(f"[Whisper] Transcription attempt (lang={lang}) error: {e}")
                continue

        return segments_out

    except Exception as e:
        print(f"[Whisper] transcribe_audio_with_whisper error: {e}")
        return []
    finally:
        # Clean up temp wav to save disk space on Render free tier
        try:
            if os.path.exists(wav_path):
                os.remove(wav_path)
        except Exception:
            pass

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
            print("[VideoEngine] 🚀 NVIDIA NVENC GPU Hardware Acceleration DETECTED & ACTIVE!")
            _DETECTED_ENCODER = ["-c:v", "h264_nvenc", "-preset", "p4", "-tune", "hq", "-b:v", "6M"]
            return _DETECTED_ENCODER
    except Exception:
        pass
        
    print("[VideoEngine] Using CPU libx264 encoder.")
    _DETECTED_ENCODER = ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "23"]
    return _DETECTED_ENCODER

def generate_srt(subtitles: list, clip_start: float = 0.0) -> str:
    """Generate SubRip (.srt) caption file content with timestamps relative to clip start."""
    lines = []
    chunk_size = 4
    for i in range(0, len(subtitles), chunk_size):
        group = subtitles[i:i + chunk_size]
        if not group:
            continue
        raw_start = float(group[0].get("start", 0))
        raw_end = float(group[-1].get("end", raw_start + 1.0))
        if raw_start >= clip_start and clip_start > 0:
            start_sec = max(0.0, raw_start - clip_start)
            end_sec = max(start_sec + 0.6, raw_end - clip_start)
        else:
            start_sec = max(0.0, raw_start)
            end_sec = max(start_sec + 0.6, raw_end)
        text = " ".join(str(item.get("word", "")).strip() for item in group).strip()
        if not text:
            continue
        
        index = (i // chunk_size) + 1
        start_srt = format_srt_timestamp(start_sec)
        end_srt = format_srt_timestamp(end_sec)
        
        lines.append(f"{index}")
        lines.append(f"{start_srt} --> {end_srt}")
        lines.append(text)
        lines.append("")
        
    return "\n".join(lines)

def format_srt_timestamp(seconds: float) -> str:
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
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

def download_and_clip_video(video_url: str, start_time: float, duration: float, layout: str = "split", subtitles: list = None, output_path: str = None) -> str:
    """
    Download and render a 9:16 short using FFmpeg.
    Layouts:
    - 'split': If streamer facecam is detected -> upper facecam zoomed & centered (720x520) + full 16:9 gameplay below.
               If NO facecam is detected -> automatically uses unified single-section 9:16 (no duplicate 2 sections).
    - 'crop': Smart center crop to 9:16 (720x1280)
    - 'blur': Blurred 9:16 ambient background with centered 16:9 video
    - 'fit': Fitted 16:9 on 9:16 canvas with clean black bars
    """
    if not output_path:
        tmp_dir = os.path.join(tempfile.gettempdir(), "godd_ai_clips")
        os.makedirs(tmp_dir, exist_ok=True)
        output_path = os.path.join(tmp_dir, f"godd_ai_{int(start_time)}_{int(duration)}.mp4")

    if not yt_dlp:
        raise RuntimeError("yt-dlp is not installed")

    # Generate SRT file if subtitles are provided
    srt_filter = ""
    srt_temp_file = None
    if subtitles and len(subtitles) > 0:
        try:
            srt_temp_file = os.path.join(tempfile.gettempdir(), f"subs_{int(start_time)}_{int(duration)}.srt")
            with open(srt_temp_file, "w", encoding="utf-8") as f:
                f.write(generate_srt(subtitles, clip_start=start_time))
            esc_srt = srt_temp_file.replace('\\', '/').replace(':', '\\:')
            srt_filter = f",subtitles='{esc_srt}':force_style='PlayResX=720,PlayResY=1280,FontName=Arial,FontSize=32,Bold=1,PrimaryColour=&H0024BFFB,OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=1,Alignment=2,MarginV=110'"
        except Exception as se:
            print(f"[FFmpeg] Notice: Could not prepare subtitles filter: {se}")
            srt_filter = ""

    # Use yt-dlp to obtain stream URL directly without needing to download gigabytes of long video
    try:
        ydl_opts = {
            'format': 'best[ext=mp4]/best/bestvideo+bestaudio',
            'extractor_args': {'youtube': {'player_client': ['android', 'ios', 'mweb']}},
            'quiet': True,
            'no_warnings': True,
        }
        stream_url = None
        video_stream_url = None
        audio_stream_url = None

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            
            # Check if direct combined stream url is available
            direct_url = info.get("url")
            if direct_url and info.get("vcodec") not in ("none", None) and info.get("acodec") not in ("none", None):
                stream_url = direct_url

            formats = info.get("formats", [])
            if not stream_url:
                # Find progressive format with both video and audio
                for f in reversed(formats):
                    if f.get("url") and f.get("vcodec") not in ("none", None) and f.get("acodec") not in ("none", None):
                        stream_url = f.get("url")
                        break

            if not stream_url:
                # Find best video stream
                for f in reversed(formats):
                    if f.get("url") and f.get("vcodec") not in ("none", None):
                        video_stream_url = f.get("url")
                        break
                # Find best audio stream
                for f in reversed(formats):
                    if f.get("url") and f.get("acodec") not in ("none", None):
                        audio_stream_url = f.get("url")
                        break

        if not stream_url and not video_stream_url:
            raise RuntimeError("Could not find playable video stream URL")

        target_stream = stream_url or video_stream_url

        # Check whether streamer facecam exists in this video
        face_info = {"has_face": False}
        if layout == "split":
            face_info = detect_facecam_in_stream(target_stream, start_time + 1.5)

        # Filter graph based on layout & facecam detection
        if layout == "split":
            if face_info.get("has_face"):
                # Streamer Facecam IS present: tightly frame and zoom into the streamer's face!
                fx = face_info["x"]
                fy = face_info["y"]
                fw = face_info["w"]
                fh = face_info["h"]
                orig_w = face_info.get("orig_w", 1920)
                orig_h = face_info.get("orig_h", 1080)

                # Head and shoulders framing: facecam fills the 720x520 upper section prominently
                cam_crop_h = int(fh * 2.6)
                cam_crop_w = int(cam_crop_h * (720.0 / 520.0))
                cam_crop_w = max(cam_crop_w, int(orig_w * 0.20))
                cam_crop_w = min(cam_crop_w, int(orig_w * 0.40))
                cam_crop_h = int(cam_crop_w * (520.0 / 720.0))

                crop_x = max(0, min(orig_w - cam_crop_w, int(fx + fw/2 - cam_crop_w/2)))
                crop_y = max(0, min(orig_h - cam_crop_h, int(fy + fh/2 - cam_crop_h/2)))

                cam_filter = f"crop={cam_crop_w}:{cam_crop_h}:{crop_x}:{crop_y},scale=720:520"
                print(f"[VideoEngine] Framing streamer facecam: {cam_filter}")

                filter_complex = (
                    "[0:v]split=2[cam_src][game_src];"
                    f"[cam_src]{cam_filter}[cam];"
                    "[game_src]scale=720:405[game];"
                    f"color=c=#0B0C10:s=720x1280:d={duration}[bg];"
                    "[bg][cam]overlay=0:0:shortest=1[bg_cam];"
                    f"[bg_cam][game]overlay=0:525:shortest=1{srt_filter}[outv]"
                )
            else:
                # User requirement: "if there is no streamer face cam in the clip then no need of 2 sections in the clip"
                print("[VideoEngine] No streamer facecam found — rendering unified single-section 9:16 short.")
                filter_complex = (
                    "[0:v]split=2[bg][fg];"
                    "[bg]scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,boxblur=25:5[bg_blurred];"
                    "[fg]scale=720:405[fg_scaled];"
                    f"[bg_blurred][fg_scaled]overlay=0:(1280-405)/2{srt_filter}[outv]"
                )
        elif layout == "blur":
            filter_complex = (
                "[0:v]split=2[bg][fg];"
                "[bg]scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,boxblur=20:5[bg_blurred];"
                "[fg]scale=720:405[fg_scaled];"
                f"[bg_blurred][fg_scaled]overlay=0:(1280-405)/2{srt_filter}[outv]"
            )
        elif layout == "fit":
            filter_complex = f"scale=720:-1,pad=720:1280:(ow-iw)/2:(oh-ih)/2:black{srt_filter}[outv]"
        else: # Default: 'crop'
            filter_complex = f"crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=720:1280{srt_filter}[outv]"

        encoder_flags = get_video_encoder_flags()

        # Run ffmpeg with fast seek (-ss before -i) and Streamer Voice audio enhancement
        if stream_url:
            cmd = [
                FFMPEG_PATH,
                "-y",
                "-ss", str(start_time),
                "-i", stream_url,
                "-t", str(duration),
                "-filter_complex", filter_complex,
                "-map", "[outv]",
                "-map", "0:a?",
                "-af", "volume=1.2,highpass=f=90,equalizer=f=1200:width_type=h:width=900:g=3.5,acompressor=threshold=-18dB:ratio=2.5:attack=5:release=50",
                *encoder_flags,
                "-c:a", "aac",
                "-b:a", "128k",
                "-movflags", "+faststart",
                output_path
            ]
        else:
            cmd = [
                FFMPEG_PATH,
                "-y",
                "-ss", str(start_time),
                "-i", video_stream_url,
                "-ss", str(start_time),
                "-i", audio_stream_url if audio_stream_url else video_stream_url,
                "-t", str(duration),
                "-filter_complex", filter_complex,
                "-map", "[outv]",
                "-map", "1:a?",
                "-af", "volume=1.2,highpass=f=90,equalizer=f=1200:width_type=h:width=900:g=3.5,acompressor=threshold=-18dB:ratio=2.5:attack=5:release=50",
                *encoder_flags,
                "-c:a", "aac",
                "-b:a", "128k",
                "-movflags", "+faststart",
                output_path
            ]

        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
        if result.returncode != 0:
            print(f"[FFmpeg] Error: {result.stderr}")
            raise RuntimeError(f"FFmpeg render failed: {result.stderr[:200]}")

        return output_path

    except Exception as e:
        print(f"[VideoEngine] Error rendering video: {e}")
        raise e
