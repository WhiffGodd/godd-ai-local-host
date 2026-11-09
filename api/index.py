import json
import urllib.parse
from http.server import BaseHTTPRequestHandler
import sys
import os

# Ensure local imports work in Vercel serverless environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from analyzer import (
        extract_youtube_id,
        get_video_metadata,
        fetch_transcript_segments,
        analyze_virality_and_cut_clips,
        synthesize_viral_clips
    )
except ImportError:
    from .analyzer import (
        extract_youtube_id,
        get_video_metadata,
        fetch_transcript_segments,
        analyze_virality_and_cut_clips,
        synthesize_viral_clips
    )

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
                    {"word": "The", "start": 147.3, "end": 147.7, "highlight": False},
                    {"word": "top", "start": 147.7, "end": 148.1, "highlight": True},
                    {"word": "creators", "start": 148.1, "end": 148.8, "highlight": True},
                    {"word": "don't", "start": 148.8, "end": 149.2, "highlight": False},
                    {"word": "wait", "start": 149.2, "end": 149.6, "highlight": False},
                    {"word": "for", "start": 149.6, "end": 150.0, "highlight": False},
                    {"word": "inspiration. 💡", "start": 150.0, "end": 151.0, "highlight": True}
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
                "full_text": "Chat, look at my hands, they are literally shaking right now. If we miss this one jump, the entire speedrun is over. Three, two, one... LET'S GOOO! WE BROKE THE RECORD!",
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

def format_srt_timestamp(seconds: float) -> str:
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"

class handler(BaseHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path.endswith("/status"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "app": "godd ai", "version": "1.0.0", "platform": "vercel"}).encode("utf-8"))
            return

        if path.endswith("/samples"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(SAMPLE_VIDEOS).encode("utf-8"))
            return

        # Serve static assets fallback
        base_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        target_file = None
        content_type = "text/plain"

        if path in ["/", "/index.html"]:
            target_file = os.path.join(base_root, "public", "index.html")
            if not os.path.exists(target_file):
                target_file = os.path.join(base_root, "index.html")
            content_type = "text/html; charset=utf-8"
        elif path == "/style.css":
            target_file = os.path.join(base_root, "public", "style.css")
            if not os.path.exists(target_file):
                target_file = os.path.join(base_root, "style.css")
            content_type = "text/css; charset=utf-8"
        elif path == "/app.js":
            target_file = os.path.join(base_root, "public", "app.js")
            if not os.path.exists(target_file):
                target_file = os.path.join(base_root, "app.js")
            content_type = "application/javascript; charset=utf-8"

        if target_file and os.path.exists(target_file):
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.end_headers()
            with open(target_file, "rb") as f:
                self.wfile.write(f.read())
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"app": "godd ai serverless api", "endpoints": ["/api/analyze", "/api/samples", "/api/status"]}).encode("utf-8"))

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            payload = {}

        if path.endswith("/analyze"):
            url = payload.get("url", "").strip()
            video_id = extract_youtube_id(url) or "sample_test_vid"

            meta = get_video_metadata(video_id, url)
            transcript = fetch_transcript_segments(video_id)
            clips = analyze_virality_and_cut_clips(
                transcript=transcript,
                video_duration=meta.get("duration", 600),
                title=meta.get("title", "")
            )

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
                    "view_count": meta.get("view_count", 250000)
                },
                "clips": clips
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode("utf-8"))
            return

        if path.endswith("/download-srt"):
            subtitles = payload.get("subtitles", [])
            lines = []
            chunk_size = 4
            for i in range(0, len(subtitles), chunk_size):
                group = subtitles[i:i + chunk_size]
                if not group:
                    continue
                start_sec = group[0]["start"]
                end_sec = group[-1]["end"]
                text = " ".join(item["word"] for item in group)
                idx = (i // chunk_size) + 1
                lines.append(f"{idx}\n{format_srt_timestamp(start_sec)} --> {format_srt_timestamp(end_sec)}\n{text}\n")
            
            srt_content = "\n".join(lines)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(srt_content.encode("utf-8"))
            return

        self.send_response(404)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"error": "Endpoint not found"}).encode("utf-8"))
