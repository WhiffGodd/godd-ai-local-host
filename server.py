import http.server
import socketserver
import json
import urllib.parse
import os
import sys
import mimetypes
import traceback
from analyzer import (
    extract_youtube_id,
    get_video_metadata,
    fetch_transcript_segments,
    analyze_virality_and_cut_clips,
    synthesize_viral_clips
)
from video_engine import generate_srt, download_and_clip_video

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

PORT = int(os.environ.get("PORT", 8080))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

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
    def end_headers(self):
        # Enable CORS and disable aggressive caching for local testing
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

        if path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "app": "godd ai", "version": "1.0.0"}).encode("utf-8"))
            return

        if path == "/api/samples":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(SAMPLE_VIDEOS).encode("utf-8"))
            return

        # Serve static files from BASE_DIR
        file_path = os.path.join(BASE_DIR, path.lstrip("/"))
        if path == "/" or not os.path.exists(file_path) or os.path.isdir(file_path):
            file_path = os.path.join(BASE_DIR, "index.html")

        if os.path.exists(file_path) and os.path.isfile(file_path):
            self.send_response(200)
            content_type, _ = mimetypes.guess_type(file_path)
            self.send_header("Content-Type", content_type or "text/plain")
            self.end_headers()
            with open(file_path, "rb") as f:
                self.wfile.write(f.read())
            return

        self.send_error(404, "File not found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            payload = {}

        if path == "/api/analyze":
            self.handle_analyze(payload)
            return

        if path == "/api/download-srt":
            self.handle_srt(payload)
            return

        if path == "/api/render-clip":
            self.handle_render_clip(payload)
            return

        self.send_error(404, "Endpoint not found")

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
            
            # 2. Fetch or synthesize transcript
            transcript = fetch_transcript_segments(video_id)
            
            # 3. Analyze virality and generate clips
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

        except Exception as e:
            traceback.print_exc()
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    def handle_srt(self, payload: dict):
        subtitles = payload.get("subtitles", [])
        srt_content = generate_srt(subtitles)
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Disposition", 'attachment; filename="godd_ai_captions.srt"')
        self.end_headers()
        self.wfile.write(srt_content.encode("utf-8"))

    def handle_render_clip(self, payload: dict):
        url = payload.get("url", "")
        start_time = float(payload.get("start", 0))
        duration = float(payload.get("duration", 30))
        layout = payload.get("layout", "crop")

        try:
            rendered_path = download_and_clip_video(
                video_url=url,
                start_time=start_time,
                duration=duration,
                layout=layout
            )
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
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True

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
