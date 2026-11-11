import json
import urllib.parse
from http.server import BaseHTTPRequestHandler
import sys
import os

# Ensure local imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from analyzer import (
        extract_youtube_id,
        get_video_metadata,
        fetch_transcript_segments,
        analyze_virality_and_cut_clips
    )
except ImportError:
    from .analyzer import (
        extract_youtube_id,
        get_video_metadata,
        fetch_transcript_segments,
        analyze_virality_and_cut_clips
    )

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            payload = {}

        url = payload.get("url", "").strip()
        video_id = extract_youtube_id(url) or "sample_test_vid"

        try:
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
                "clips": clips,
                "transcript_available": bool(transcript)
            }

            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode("utf-8"))
        except Exception:
            self.send_response(500)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Could not analyze the video."}).encode("utf-8"))

    def do_GET(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"endpoint": "/api/analyze", "method": "POST"}).encode("utf-8"))
