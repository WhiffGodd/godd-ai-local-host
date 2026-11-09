import json
from http.server import BaseHTTPRequestHandler

def format_srt_timestamp(seconds: float) -> str:
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"

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
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Disposition", 'attachment; filename="godd_ai_captions.srt"')
        self.end_headers()
        self.wfile.write(srt_content.encode("utf-8"))

    def do_GET(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"SRT Download Endpoint")
