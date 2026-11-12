import http.server
import socketserver
import socket
import secrets
from collections import OrderedDict
from html import escape
from http.cookies import CookieError, SimpleCookie
import json
import urllib.parse
import os
import sys
import mimetypes
import traceback
import re
import math
import queue
from threading import BoundedSemaphore
from render_jobs import RenderJobs
from source_uploads import SourceUploads, MAX_CHUNK_BYTES, validate_uploaded_video
from api.youtube_access import download_error_response
from api.clip_boundaries import MAX_CLIP_SECONDS
from api.clip_metadata import add_clip_metadata
from api.youtube_upload import (
    CALLBACK_PATH, SESSION_AGE, YouTubeConnections, YouTubeUploadError, set_video_thumbnail, upload_metadata, upload_video,
)
from analyzer import (
    extract_youtube_id,
    get_video_metadata,
    fetch_transcript_segments,
    analyze_virality_and_cut_clips
)
from video_engine import capture_thumbnail, generate_srt, download_and_clip_video, preview_facecam, transcribe_audio_with_whisper, WHISPER_AVAILABLE

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

PORT = int(os.environ.get("PORT", 8080))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAPTION_RESULTS = OrderedDict()
SOURCE_UPLOADS = SourceUploads()
YOUTUBE = YouTubeConnections()
YOUTUBE_COOKIE = "godd_youtube"
THUMBNAIL_SLOTS = BoundedSemaphore(2)


def download_filename(title, start):
    stem = re.sub(r"[^a-zA-Z0-9_\s-]", "", title if isinstance(title, str) else "")
    stem = re.sub(r"[-\s]+", "_", stem.strip())[:100]
    if not stem or re.fullmatch(r"con|prn|aux|nul|com[0-9]|lpt[0-9]", stem, flags=re.I):
        stem = f"clip_{round(start)}s"
    return f"{stem}.mp4"


def validate_render_payload(payload):
    host = urllib.parse.urlparse(payload.get("url", "")).hostname
    if host not in ("youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "music.youtube.com"):
        raise ValueError("Please provide a YouTube video URL.")
    if urllib.parse.urlparse(payload["url"]).scheme != "https" or not extract_youtube_id(payload["url"]):
        raise ValueError("Please provide a valid HTTPS YouTube video URL.")
    start = float(payload.get("start", 0))
    duration = float(payload.get("duration", 30))
    if not math.isfinite(start) or start < 0 or not math.isfinite(duration) or not 1 <= round(duration, 6) <= MAX_CLIP_SECONDS:
        raise ValueError("Choose a clip between 1 second and 2 minutes with a valid start time.")
    return {**payload, "start": start, "duration": duration}


def run_export(payload):
    source_path = uploaded_source_path(payload)
    return download_and_clip_video(
        video_url=payload["url"], start_time=payload["start"], duration=payload["duration"],
        layout=payload.get("layout", "split"), subtitle_style=payload.get("subtitle_style", "beast"),
        subtitles=payload.get("subtitles", []), video_subtitles=payload.get("video_subtitles", []),
        caption_source=payload.get("caption_source", "auto"), local_source_path=source_path)


def publish_to_youtube(owner, payload, path):
    access = YOUTUBE.access_token(owner, payload["youtube_channel"])
    return upload_video(path, access, payload["youtube_metadata"])


def uploaded_source_path(payload):
    if payload.get("upload_id"):
        return validate_uploaded_video(SOURCE_UPLOADS.completed_path(payload["upload_id"]))
    return None


def thumbnail_time(value):
    try:
        timestamp = float(value)
    except (TypeError, ValueError):
        raise ValueError("Enter a valid thumbnail timestamp.") from None
    if not math.isfinite(timestamp) or timestamp < 0:
        raise ValueError("Enter a valid thumbnail timestamp.")
    return timestamp


def apply_youtube_thumbnail(owner, payload, path, video_id):
    timestamp = payload["thumbnail_time"]
    try:
        image = capture_thumbnail(payload["url"], timestamp, uploaded_source_path(payload))
    except Exception:
        relative = timestamp - payload["start"]
        if not 0 <= relative < payload["duration"]:
            return "Could not capture the selected thumbnail. The video is already uploaded."
        image = capture_thumbnail(payload["url"], relative, path)
    access = YOUTUBE.access_token(owner, payload["youtube_channel"])
    return set_video_thumbnail(video_id, access, image)


EXPORT_JOBS = RenderJobs(run_export, publisher=publish_to_youtube, thumbnailer=apply_youtube_thumbnail)

SAMPLE_VIDEOS = [
    {
        "id": "sample_huberman",
        "title": "Andrew Huberman & Rick Rubin: How Creative Genius Actually Works",
        "author": "Huberman Lab",
        "thumbnail": "https://images.unsplash.com/photo-1590602847861-f357a9332bbc?w=800&auto=format&fit=crop&q=80",
        "duration": 5420,
        "sample_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "clips": [
            {
                "id": "clip_1",
                "rank": 1,
                "title": "The Brutal Secret To Creative Genius 🧠",
                "hook": "Everyone thinks ideas come from motivation, but they're completely wrong...",
                "start": 142.0,
                "end": 182.0,
                "duration": "0:40",
                "duration_sec": 40.0,
                "virality_score": 98,
                "virality_badge": "🔥 Viral Hit",
                "viral_reasons": ["High curiosity gap in hook", "98% predicted viewer retention", "Punchy takeaway climax"],
                "tags": ["Mindset", "Genius", "Top Pick"],
                "full_text": "Everyone thinks ideas come from motivation, but they're completely wrong. Motivation is an emotional wave that dies in ten minutes. The top creators don't wait for inspiration. They set up non-negotiable friction boundaries so the subconscious brain is forced to solve the dilemma.",
                "subtitles": [
                    {"word": "Everyone", "start": 142.0, "end": 142.5, "highlight": False},
                    {"word": "thinks", "start": 142.5, "end": 142.9, "highlight": False},
                    {"word": "ideas", "start": 142.9, "end": 143.4, "highlight": False},
                    {"word": "come", "start": 143.4, "end": 143.8, "highlight": False},
                    {"word": "from", "start": 143.8, "end": 144.1, "highlight": False},
                    {"word": "motivation,", "start": 144.1, "end": 144.8, "highlight": True},
                    {"word": "but", "start": 145.0, "end": 145.3, "highlight": False},
                    {"word": "they're", "start": 145.3, "end": 145.7, "highlight": False},
                    {"word": "completely", "start": 145.7, "end": 146.2, "highlight": True},
                    {"word": "wrong.", "start": 146.2, "end": 147.0, "highlight": True},
                    {"word": "Motivation", "start": 147.3, "end": 147.9, "highlight": False},
                    {"word": "dies", "start": 147.9, "end": 148.4, "highlight": False},
                    {"word": "in", "start": 148.4, "end": 148.7, "highlight": False},
                    {"word": "ten", "start": 148.7, "end": 149.1, "highlight": False},
                    {"word": "minutes. ⏳", "start": 149.1, "end": 149.8, "highlight": False},
                    {"word": "The", "start": 150.1, "end": 150.3, "highlight": False},
                    {"word": "top", "start": 150.3, "end": 150.7, "highlight": True},
                    {"word": "creators", "start": 150.7, "end": 151.3, "highlight": True},
                    {"word": "don't", "start": 151.3, "end": 151.7, "highlight": False},
                    {"word": "wait", "start": 151.7, "end": 152.1, "highlight": False},
                    {"word": "for", "start": 152.1, "end": 152.4, "highlight": False},
                    {"word": "inspiration. 💡", "start": 152.4, "end": 153.2, "highlight": True},
                    {"word": "They", "start": 153.5, "end": 153.8, "highlight": False},
                    {"word": "force", "start": 153.8, "end": 154.3, "highlight": True},
                    {"word": "the", "start": 154.3, "end": 154.6, "highlight": False},
                    {"word": "mind", "start": 154.6, "end": 155.1, "highlight": False},
                    {"word": "to", "start": 155.1, "end": 155.4, "highlight": False},
                    {"word": "deliver", "start": 155.4, "end": 156.0, "highlight": False},
                    {"word": "pure", "start": 156.0, "end": 156.5, "highlight": True},
                    {"word": "gold. 🔥", "start": 156.5, "end": 157.5, "highlight": True}
                ]
            },
            {
                "id": "clip_2",
                "rank": 2,
                "title": "Why 99% Of People Burn Out Early ⚠️",
                "hook": "Stop waking up and checking your screen first thing in the morning!",
                "start": 410.0,
                "end": 445.0,
                "duration": "0:35",
                "duration_sec": 35.0,
                "virality_score": 95,
                "virality_badge": "🔥 Viral Hit",
                "viral_reasons": ["Urgent alert trigger", "High emotional relatability", "Punchy 35-sec runtime"],
                "tags": ["Dopamine", "Health", "Trending"],
                "full_text": "Stop waking up and checking your phone first thing. When you flood your dopamine receptors at 7:00 AM with infinite scroll, you've exhausted your executive focus for the next eight hours. Sunlight in your eyes before screen time changes your entire biochemical state.",
                "subtitles": [
                    {"word": "Stop", "start": 410.0, "end": 410.4, "highlight": True},
                    {"word": "waking", "start": 410.4, "end": 410.8, "highlight": False},
                    {"word": "up", "start": 410.8, "end": 411.1, "highlight": False},
                    {"word": "and", "start": 411.1, "end": 411.3, "highlight": False},
                    {"word": "checking", "start": 411.3, "end": 411.8, "highlight": False},
                    {"word": "your", "start": 411.8, "end": 412.1, "highlight": False},
                    {"word": "phone! 📱", "start": 412.1, "end": 412.9, "highlight": True},
                    {"word": "You're", "start": 413.2, "end": 413.6, "highlight": False},
                    {"word": "destroying", "start": 413.6, "end": 414.2, "highlight": True},
                    {"word": "your", "start": 414.2, "end": 414.5, "highlight": False},
                    {"word": "dopamine", "start": 414.5, "end": 415.1, "highlight": True},
                    {"word": "levels", "start": 415.1, "end": 415.6, "highlight": False},
                    {"word": "before", "start": 415.6, "end": 416.0, "highlight": False},
                    {"word": "the", "start": 416.0, "end": 416.2, "highlight": False},
                    {"word": "day", "start": 416.2, "end": 416.6, "highlight": False},
                    {"word": "even", "start": 416.6, "end": 417.0, "highlight": False},
                    {"word": "begins! 🤯", "start": 417.0, "end": 418.0, "highlight": True}
                ]
            },
            {
                "id": "clip_3",
                "rank": 3,
                "title": "The $10 Million Dollar Rule 💰",
                "hook": "If you master this one skill, you will never be broke again.",
                "start": 820.0,
                "end": 862.0,
                "duration": "0:42",
                "duration_sec": 42.0,
                "virality_score": 92,
                "virality_badge": "🔥 Viral Hit",
                "viral_reasons": ["Financial aspiration hook", "Strong direct address", "High bookmark value"],
                "tags": ["Finance", "Skills", "Growth"],
                "full_text": "If you master this one skill, you will never be broke again. People chase products, but wealth chases leverage. When you learn how to articulate ideas clearly and command an audience, every industry opens its doors to you.",
                "subtitles": [
                    {"word": "Master", "start": 820.0, "end": 820.5, "highlight": True},
                    {"word": "this", "start": 820.5, "end": 820.8, "highlight": False},
                    {"word": "one", "start": 820.8, "end": 821.2, "highlight": True},
                    {"word": "skill,", "start": 821.2, "end": 821.8, "highlight": True},
                    {"word": "and", "start": 822.0, "end": 822.3, "highlight": False},
                    {"word": "you'll", "start": 822.3, "end": 822.7, "highlight": False},
                    {"word": "never", "start": 822.7, "end": 823.1, "highlight": True},
                    {"word": "be", "start": 823.1, "end": 823.4, "highlight": False},
                    {"word": "broke", "start": 823.4, "end": 824.0, "highlight": True},
                    {"word": "again. 💰", "start": 824.0, "end": 825.0, "highlight": True}
                ]
            }
        ]
    },
    {
        "id": "sample_streamer",
        "title": "Insane Livestream Reaction: World Record Attempt Live",
        "author": "Godd Gaming Live",
        "thumbnail": "https://images.unsplash.com/photo-1542751371-adc38448a05e?w=800&auto=format&fit=crop&q=80",
        "duration": 3600,
        "sample_url": "https://www.youtube.com/watch?v=live_stream_example",
        "clips": [
            {
                "id": "clip_stream_1",
                "rank": 1,
                "title": "HE ACTUALLY PULLED IT OFF?! 🤯🔥",
                "hook": "Chat, look at my hands, they are literally shaking right now...",
                "start": 620.0,
                "end": 655.0,
                "duration": "0:35",
                "duration_sec": 35.0,
                "virality_score": 99,
                "virality_badge": "🔥 Viral Hit",
                "viral_reasons": ["Extreme live suspense", "High viewer tension", "Peak spontaneous reaction"],
                "tags": ["Gaming", "Clutch", "World Record"],
                "full_text": "Chat, look at my hands, they are literally shaking right now. If we miss this one jump, the entire ten-hour speedrun is officially over. Three, two, one... LET'S GOOO! NO WAY! WE BROKE THE RECORD!",
                "subtitles": [
                    {"word": "Chat,", "start": 620.0, "end": 620.5, "highlight": True},
                    {"word": "look", "start": 620.5, "end": 620.8, "highlight": False},
                    {"word": "at", "start": 620.8, "end": 621.1, "highlight": False},
                    {"word": "my", "start": 621.1, "end": 621.3, "highlight": False},
                    {"word": "hands! 😱", "start": 621.3, "end": 622.0, "highlight": True},
                    {"word": "Three,", "start": 622.5, "end": 623.0, "highlight": False},
                    {"word": "two,", "start": 623.0, "end": 623.5, "highlight": False},
                    {"word": "one...", "start": 623.5, "end": 624.2, "highlight": False},
                    {"word": "LET'S", "start": 624.5, "end": 625.0, "highlight": True},
                    {"word": "GOOO! 🔥", "start": 625.0, "end": 626.0, "highlight": True}
                ]
            }
        ]
    }
]

class GoddAIRequestHandler(http.server.SimpleHTTPRequestHandler):
    def log_request(self, code="-", size="-"):
        if urllib.parse.urlsplit(self.path).path == CALLBACK_PATH:
            self.log_message('"%s %s %s" %s %s', self.command, CALLBACK_PATH, self.request_version, code, size)
        else:
            super().log_request(code, size)

    def youtube_session(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except CookieError:
            return None
        return cookie[YOUTUBE_COOKIE].value if YOUTUBE_COOKIE in cookie else None

    def youtube_cookie(self, session_id="", max_age=SESSION_AGE):
        secure = "; Secure" if YOUTUBE.origin.startswith("https:") else ""
        return f"{YOUTUBE_COOKIE}={session_id}; Path=/api/youtube; Max-Age={max_age}; HttpOnly; SameSite=Lax{secure}"

    def youtube_json(self, status, data, cookie=None):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def youtube_host_matches(self):
        return YOUTUBE.enabled and self.headers.get("Host") == urllib.parse.urlsplit(YOUTUBE.origin).netloc

    def youtube_callback(self, query):
        try:
            if not self.youtube_host_matches():
                raise YouTubeUploadError("Open the studio at its configured address before connecting.")
            YOUTUBE.complete(self.youtube_session(), query.get("state", [""])[0], query.get("code", [""])[0])
        except YouTubeUploadError as error:
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write((f"<!doctype html><html lang='en'><meta charset='utf-8'><title>YouTube connection</title>"
                              f"<p>{escape(str(error))}</p><a href='/?youtube=retry'>Return to the clip studio</a>"
                              "</html>").encode())
            return
        self.send_response(303)
        self.send_header("Location", "/?youtube=connected")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()

    def handle_youtube_post(self, path, payload):
        if not self.youtube_host_matches():
            self.youtube_json(503, {"error": "YouTube connection is unavailable at this address."})
            return
        if self.headers.get("Origin") != YOUTUBE.origin:
            self.youtube_json(403, {"error": "Open the studio to make this request."})
            return
        owner = self.youtube_session()
        if path == "/api/youtube/connect":
            try:
                owner, url = YOUTUBE.begin(owner)
                self.youtube_json(200, {"url": url}, self.youtube_cookie(owner))
            except YouTubeUploadError as error:
                self.youtube_json(429, {"error": str(error)})
            return
        if path == "/api/youtube/disconnect":
            YOUTUBE.disconnect(owner)
            self.youtube_json(200, {"connected": False}, self.youtube_cookie(max_age=0))
            return
        channel = YOUTUBE.channel(owner)
        if not channel:
            self.youtube_json(401, {"error": "Connect your YouTube channel first."})
            return
        if payload.get("channel_id") != channel["id"]:
            self.youtube_json(409, {"error": "The connected YouTube channel changed. Review the channel and try again."})
            return
        try:
            request_id = payload.get("request_id", "")
            if not isinstance(request_id, str) or not re.fullmatch(r"[\w-]{16,80}", request_id, flags=re.ASCII):
                raise ValueError("Could not identify this upload request. Please try again.")
            validated = validate_render_payload(payload)
            if payload.get("thumbnail_time") is not None:
                validated["thumbnail_time"] = thumbnail_time(payload["thumbnail_time"])
            if payload.get("upload_id"):
                SOURCE_UPLOADS.completed_path(payload["upload_id"])
            validated.update(youtube_metadata=upload_metadata(payload), youtube_channel=channel["id"])
            job = EXPORT_JOBS.submit(validated, owner=owner, request_id=request_id)
            self.youtube_json(202, job)
        except (TypeError, AttributeError):
            self.youtube_json(400, {"error": "Provide a valid clip and YouTube upload settings."})
        except ValueError as error:
            self.youtube_json(400, {"error": str(error)})
        except queue.Full:
            self.youtube_json(429, {"error": "The export queue is full. Try again shortly."})

    def end_headers(self):
        # Enable CORS and disable aggressive caching for local testing
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Range, Authorization, X-Requested-With, Accept")
        self.send_header("Access-Control-Expose-Headers", "Content-Disposition, Content-Length, Content-Type, X-Captions-URL")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/youtube/status":
            enabled = self.youtube_host_matches()
            self.youtube_json(200, {"enabled": enabled,
                                    "channel": YOUTUBE.channel(self.youtube_session()) if enabled else None})
            return
        if path == CALLBACK_PATH:
            self.youtube_callback(urllib.parse.parse_qs(parsed.query))
            return
        if path.startswith("/api/youtube/uploads/"):
            owner = self.youtube_session()
            job = EXPORT_JOBS.snapshot(path.rsplit("/", 1)[-1], owner) if owner and self.youtube_host_matches() else None
            if job:
                self.youtube_json(200, job)
            else:
                self.youtube_json(404, {"error": "This upload has expired or is unavailable."})
            return

        if path in ("/api/status", "/healthz"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "app": "godd ai backend", "version": "1.5.0", "caption_renderer": "styled-ass"}).encode("utf-8"))
            return

        if path == "/api/samples":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(SAMPLE_VIDEOS).encode("utf-8"))
            return

        if path == "/api/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "service": "godd-ai", "mode": "cloud" if os.environ.get("RENDER") else "local"}).encode("utf-8"))
            return

        if path == "/api/clip-captions":
            token = urllib.parse.parse_qs(parsed.query).get("id", [""])[0]
            captions = CAPTION_RESULTS.get(token)
            if captions is None:
                self.send_error(404, "Caption result expired")
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(captions, ensure_ascii=False).encode("utf-8"))
            return

        # Direct browser download endpoint via GET
        if path == "/api/render-clip":
            query = urllib.parse.parse_qs(parsed.query)
            url = query.get("url", [""])[0]
            start_time = query.get("start", [0])[0]
            duration = query.get("duration", [30])[0]
            layout = query.get("layout", ["split"])[0]
            title = query.get("title", [""])[0]
            payload = {
                "url": url,
                "start": start_time,
                "duration": duration,
                "layout": layout,
                "title": title,
                "stream": True,
                "subtitles": [],
                "subtitle_style": query.get("subtitle_style", ["source"])[0]
            }
            self.handle_render_clip(payload)
            return

        if path.startswith("/api/exports/"):
            parts = path.strip("/").split("/")
            token = parts[2] if len(parts) >= 3 else ""
            status = EXPORT_JOBS.snapshot(token)
            if status is None:
                self.send_error(404, "Export expired or not found")
                return
            if len(parts) == 3:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(status).encode())
                return
            output = EXPORT_JOBS.completed_path(token)
            if not output:
                self.send_error(409, "Export is not ready")
                return
            if parts[3] == "captions":
                caption_path = output + ".captions.json"
                captions = {"words": []}
                if os.path.exists(caption_path):
                    with open(caption_path, encoding="utf-8") as f:
                        captions = json.load(f)
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(captions, ensure_ascii=False).encode("utf-8"))
                return
            if parts[3] == "download":
                self.send_response(200)
                self.send_header("Content-Type", "video/mp4")
                filename = status.get("filename", "godd_ai_clip.mp4")
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
                self.send_header("Content-Length", str(os.path.getsize(output)))
                self.send_header("X-Captions-URL", f"/api/exports/{token}/captions")
                self.end_headers()
                with open(output, "rb") as f:
                    while chunk := f.read(65536):
                        self.wfile.write(chunk)
                return
            self.send_error(404)
            return

        static_assets = {"/": "index.html", "/index.html": "index.html",
                         "/app.js": "app.js", "/style.css": "style.css",
                         "/youtube-studio.js": "public/youtube-studio.js",
                         "/privacy.html": "public/privacy.html"}
        asset = static_assets.get(path)
        if asset is None:
            self.send_error(404, "File not found")
            return
        file_path = os.path.join(BASE_DIR, asset)
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(file_path)[0] or "application/octet-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        with open(file_path, "rb") as f:
            self.wfile.write(f.read())

    def do_PUT(self):
        parsed = urllib.parse.urlparse(self.path)
        parts = parsed.path.strip("/").split("/")
        if len(parts) != 3 or parts[:2] != ["api", "source-uploads"]:
            self.send_error(404)
            return
        try:
            self.connection.settimeout(90)
            offset = int(urllib.parse.parse_qs(parsed.query).get("offset", ["0"])[0])
            length = int(self.headers.get("Content-Length", "0"))
            received = SOURCE_UPLOADS.append(parts[2], offset, self.rfile, length)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"received": received}).encode())
        except (ValueError, OSError) as error:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(error)}).encode())

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        if content_length < 0 or content_length > 2_000_000:
            self.send_error(413, "Request is too large")
            return
        body = self.rfile.read(content_length)

        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
            if not isinstance(payload, dict):
                raise ValueError("Request must be an object")
        except Exception:
            payload = {}

        if path in ("/api/youtube/connect", "/api/youtube/disconnect", "/api/youtube/uploads"):
            self.handle_youtube_post(path, payload)
            return

        if path == "/api/source-uploads":
            try:
                token = SOURCE_UPLOADS.create(payload.get("size"))
                self.send_response(201)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"id": token, "chunk_size": MAX_CHUNK_BYTES}).encode())
            except ValueError as error:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(error)}).encode())
            return

        if path == "/api/exports":
            try:
                validated = validate_render_payload(payload)
                validated["filename"] = download_filename(payload.get("title"), validated["start"])
                if payload.get("upload_id"):
                    SOURCE_UPLOADS.completed_path(payload["upload_id"])
                job = EXPORT_JOBS.submit(validated)
                self.send_response(202)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(job).encode())
            except (ValueError, TypeError):
                self.send_error(400, "Provide a valid YouTube URL and a clip of 1 second to 2 minutes")
            except queue.Full:
                self.send_response(429)
                self.send_header("Content-Type", "application/json")
                self.send_header("Retry-After", "30")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "The export queue is full. Please try again shortly."}).encode())
            return

        if path == "/api/analyze":
            try:
                validate_render_payload({**payload, "start": 0, "duration": 1})
            except (ValueError, TypeError):
                self.send_error(400, "Provide a valid HTTPS YouTube URL")
                return
            self.handle_analyze(payload)
            return

        if path == "/api/facecam":
            try:
                clip = validate_render_payload(payload)
            except (ValueError, TypeError):
                self.send_error(400, "Provide a valid YouTube URL and a clip of 1 second to 2 minutes")
                return
            try:
                region = preview_facecam(clip["url"], clip["start"], clip["duration"])
            except Exception as error:
                print(f"[FaceCam] Preview unavailable: {error}")
                region = None
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"facecam": region}).encode())
            return

        if path == "/api/thumbnail":
            self.handle_thumbnail(payload)
            return

        if path == "/api/download-srt":
            self.handle_srt(payload)
            return

        if path == "/api/render-clip":
            self.handle_render_clip(payload)
            return

        self.send_error(404, "Endpoint not found")

    def handle_thumbnail(self, payload):
        try:
            source = validate_render_payload({**payload, "start": 0, "duration": 1})
            timestamp = thumbnail_time(payload.get("timestamp"))
            local_path = uploaded_source_path(payload)
        except (ValueError, TypeError, AttributeError) as error:
            self.youtube_json(400, {"error": str(error)})
            return
        if not THUMBNAIL_SLOTS.acquire(blocking=False):
            self.youtube_json(429, {"error": "Thumbnail capture is busy. Try again shortly."})
            return
        try:
            image = capture_thumbnail(source["url"], timestamp, local_path)
        except Exception:
            self.youtube_json(502, {"error": "Could not load this source frame. Try another timestamp or use the original video file."})
            return
        finally:
            THUMBNAIL_SLOTS.release()
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(image)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(image)

    def handle_analyze(self, payload: dict):
        url = payload.get("url", "").strip()
        if not url:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "No URL provided"}).encode("utf-8"))
            return

        video_id = extract_youtube_id(url)
        if not video_id:
            # Check if this matches a sample or direct test
            video_id = "sample_test_vid"

        print(f"[godd ai] Analyzing video URL: {url} (ID: {video_id})")

        try:
            # 1. Fetch metadata
            meta = get_video_metadata(video_id, url)
            
            # 2. Fetch transcript using YouTube API + yt-dlp real timedtext
            transcript = fetch_transcript_segments(video_id, url=url, video_title=meta.get("title", ""))
            
            # 3. Analyze virality and generate clips (timestamps + YouTube ASR subtitles)
            clips = analyze_virality_and_cut_clips(
                transcript=transcript,
                video_duration=meta.get("duration", 600),
                title=meta.get("title", ""),
                chapters=meta.get("chapters", [])
            )

            # Response returned immediately — fast & reliable (2s response time)
            response_data = {
                "success": True,
                "video": {
                    "id": video_id,
                    "url": url,
                    "title": meta.get("title", "Viral Video Stream"),
                    "author": meta.get("author", "Creator"),
                    "thumbnail": meta.get("thumbnail", f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"),
                    "duration": meta.get("duration", 600),
                    "duration_formatted": f"{int(meta.get('duration', 600) // 60)}:{int(meta.get('duration', 600) % 60):02d}",
                    "view_count": meta.get("view_count", 250000),
                    "recommended_layout": "split"
                },
                "clips": add_clip_metadata(clips, meta.get("title", ""), meta.get("author", ""),
                                           f"https://www.youtube.com/watch?v={video_id}"),
                "transcript_available": bool(transcript)
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode("utf-8"))

        except Exception as e:
            traceback.print_exc()
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    def handle_srt(self, payload: dict):
        subtitles = payload.get("subtitles", [])
        video_subtitles = payload.get("video_subtitles", [])
        clip_start = float(payload.get("start", 0))
        srt_content = generate_srt(subtitles, clip_start=clip_start, video_subtitles=video_subtitles)
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Disposition", 'attachment; filename="godd_ai_captions.srt"')
        self.end_headers()
        self.wfile.write(srt_content.encode("utf-8"))

    def handle_render_clip(self, payload: dict):
        try:
            payload = validate_render_payload(payload)
        except (ValueError, TypeError, AttributeError):
            self.send_error(400, "Provide a valid YouTube URL and a clip of 1 second to 2 minutes")
            return
        if os.environ.get("RENDER"):
            self.send_error(410, "Use the background export endpoint /api/exports")
            return
        url = payload.get("url", "")
        start_time = payload["start"]
        duration = payload["duration"]
        layout = payload.get("layout", "split")
        subtitles = payload.get("subtitles", [])
        subtitle_style = payload.get("subtitle_style", "source")
        video_subtitles = payload.get("video_subtitles", [])

        print(f"[VideoEngine] Rendering 1080p clip: URL={url}, Start={start_time}s, Dur={duration}s, Layout={layout}, Style={subtitle_style}, VideoSubtitles={len(video_subtitles)} lines, Subtitles={len(subtitles)} words")

        try:
            rendered_path = download_and_clip_video(
                video_url=url,
                start_time=start_time,
                duration=duration,
                layout=layout,
                subtitles=subtitles,
                subtitle_style=subtitle_style,
                video_subtitles=video_subtitles,
                caption_source=payload.get("caption_source", "auto")
            )

            caption_token = None
            if os.path.exists(rendered_path + ".captions.json"):
                with open(rendered_path + ".captions.json", encoding="utf-8") as f:
                    measured = json.load(f)
                caption_token = secrets.token_urlsafe(18)
                CAPTION_RESULTS[caption_token] = measured
                while len(CAPTION_RESULTS) > 32:
                    CAPTION_RESULTS.popitem(last=False)

            # Stream the rendered MP4 file directly to the client with clean title filename
            if payload.get("stream", True):
                file_size = os.path.getsize(rendered_path)
                filename = download_filename(payload.get("title"), start_time)

                self.send_response(200)
                self.send_header("Content-Type", "video/mp4")
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
                self.send_header("Content-Length", str(file_size))
                if caption_token:
                    self.send_header("X-Captions-URL", f"/api/clip-captions?id={caption_token}")
                self.end_headers()
                with open(rendered_path, "rb") as f:
                    while True:
                        chunk = f.read(65536)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                return

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": True,
                "file_path": rendered_path,
                "message": "Render completed successfully"
            }).encode("utf-8"))
        except Exception as e:
            traceback.print_exc()
            status, code, message = download_error_response(e)
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": message, "code": code}).encode("utf-8"))

class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    # Windows SO_REUSEADDR can let multiple workers bind the same port and
    # serve stale code unpredictably. Keep exactly one local backend owner.
    allow_reuse_address = os.name != "nt"

    def server_bind(self):
        if os.name == "nt":
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

def run():
    server_address = ('', PORT)
    httpd = ThreadedHTTPServer(server_address, GoddAIRequestHandler)
    print("\n" + "=" * 55)
    print(f"[godd ai] Turn Videos into Viral Shorts & Reels")
    print(f"[godd ai] Server running at: http://localhost:{PORT}")
    print(f"[godd ai] 100% Free Forever - No Watermark - Instant AI Shorts")
    print("=" * 55 + "\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down godd ai server...")
        httpd.server_close()

if __name__ == '__main__':
    run()
