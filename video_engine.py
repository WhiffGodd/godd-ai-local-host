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

    # Filter graph based on layout
    if layout == "blur":
        # Split filter: background scaled & blurred to 1080x1920, foreground scaled to fit width 1080
        filter_complex = (
            "[0:v]split=2[bg][fg];"
            "[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25:5[bg_blurred];"
            "[fg]scale=1080:-1[fg_scaled];"
            "[bg_blurred][fg_scaled]overlay=(W-w)/2:(H-h)/2[outv]"
        )
    elif layout == "fit":
        filter_complex = "scale=1080:-1,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black[outv]"
    else: # Default: 'crop'
        filter_complex = "crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920[outv]"

    # Use yt-dlp to obtain stream URL directly without needing to download gigabytes of long video
    try:
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'quiet': True,
            'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            stream_url = info.get("url")
            
            # If separated audio/video
            if not stream_url and "formats" in info:
                # Pick best mp4 format
                for f in reversed(info["formats"]):
                    if f.get("vcodec") != "none" and f.get("acodec") != "none":
                        stream_url = f.get("url")
                        break
                        
        if not stream_url:
            raise RuntimeError("Could not find direct playable stream URL")

        # Run ffmpeg with fast seek (-ss before -i)
        cmd = [
            FFMPEG_PATH,
            "-y",
            "-ss", str(start_time),
            "-i", stream_url,
            "-t", str(duration),
            "-filter_complex", filter_complex,
            "-map", "[outv]",
            "-map", "0:a?",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "22",
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
