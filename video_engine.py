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

def generate_srt(subtitles: list) -> str:
    """Generate SubRip (.srt) caption file content."""
    lines = []
    # Group words into 3-5 word subtitle lines for readability
    chunk_size = 4
    for i in range(0, len(subtitles), chunk_size):
        group = subtitles[i:i + chunk_size]
        if not group:
            continue
        start_sec = group[0]["start"]
        end_sec = group[-1]["end"]
        text = " ".join(item["word"] for item in group)
        
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

def download_and_clip_video(video_url: str, start_time: float, duration: float, layout: str = "crop", output_path: str = None) -> str:
    """
    Download and render a 9:16 short using FFmpeg.
    Layouts:
    - 'crop': Smart center crop to 9:16 (1080x1920)
    - 'blur': Blurred 9:16 background with centered video (popular podcast style)
    - 'fit': Fitted 16:9 on 9:16 canvas with clean black bars
    """
    if not output_path:
        tmp_dir = os.path.join(tempfile.gettempdir(), "godd_ai_clips")
        os.makedirs(tmp_dir, exist_ok=True)
        output_path = os.path.join(tmp_dir, f"godd_ai_{int(start_time)}_{int(duration)}.mp4")

    if not yt_dlp:
        raise RuntimeError("yt-dlp is not installed")

    # Filter graph based on layout (720x1280 vertical resolution for speed & HD quality)
    if layout == "blur":
        filter_complex = (
            "[0:v]split=2[bg][fg];"
            "[bg]scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,boxblur=20:5[bg_blurred];"
            "[fg]scale=720:-1[fg_scaled];"
            "[bg_blurred][fg_scaled]overlay=(W-w)/2:(H-h)/2[outv]"
        )
    elif layout == "fit":
        filter_complex = "scale=720:-1,pad=720:1280:(ow-iw)/2:(oh-ih)/2:black[outv]"
    else: # Default: 'crop'
        filter_complex = "crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=720:1280[outv]"

    # Use yt-dlp to obtain stream URL directly without needing to download gigabytes of long video
    try:
        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'extractor_args': {'youtube': {'player_client': ['android', 'ios', 'mweb']}},
            'quiet': True,
            'no_warnings': True,
        }
        stream_url = None
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            stream_url = info.get("url")

            # If separated audio/video formats
            if not stream_url and "formats" in info:
                for f in reversed(info["formats"]):
                    if f.get("url") and f.get("protocol", "").startswith("http"):
                        stream_url = f.get("url")
                        break
                        
        if not stream_url:
            raise RuntimeError("Could not find direct playable stream URL")

        # Run ffmpeg with fast seek (-ss before -i) and Streamer Voice audio enhancement
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
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "23",
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
