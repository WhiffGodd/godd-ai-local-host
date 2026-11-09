import json
from http.server import BaseHTTPRequestHandler

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

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(SAMPLE_VIDEOS).encode("utf-8"))
