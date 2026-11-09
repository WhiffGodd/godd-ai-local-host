# ⚡ godd ai

> Turn long videos into viral TikToks, Reels & Shorts with AI — **100% Free Forever**.  
> The free, open alternative to **Klap.app** and **Opus Clip**.

---

## ✨ Features

- **🎯 AI Virality Engine**: Analyzes transcripts and audio dynamics to detect the highest-retention moments (curiosity hooks in the first 3 seconds, emotional spikes, punchlines, and high-energy laughter).
- **📱 Smart 9:16 Auto-Reframing**: Converts standard horizontal 16:9 YouTube videos and live streams into flawless vertical shorts (Supports *Smart Center Crop*, *Podcast Background Blur*, and *Letterbox Fit*).
- **🔥 Dynamic Animated Karaoke Subtitles**:
  - **Hormozi Style**: Bold yellow/green words with thick black stroke.
  - **MrBeast Style**: High-energy cyan and orange text with animated rotation.
  - **Cyber Glow**: Futuristic neon green aura.
  - **Minimal Clean**: Crisp white text in translucent capsules.
  - Auto-generated contextual emojis (`💰`, `🤯`, `🔥`, `🚀`, `💡`).
- **📱 Smartphone Studio Preview**: Interactive 9:16 mobile mockup with real-time word-by-word karaoke synchronization, scrubber, and video playback.
- **⚡ Dual Export Modes**:
  - **Client-Side Instant Export**: Direct in-browser recording via WebCodecs/Canvas to WebM/MP4 with zero server waiting queues.
  - **Server-Side FFmpeg Render**: Native 1080x1920 60fps MP4 encoding powered by `imageio-ffmpeg`.
- **📄 SRT Subtitle & Script Export**: Download `.srt` subtitle tracks or copy the full hook and script in one click.
- **🚫 100% Free & No Watermarks**: No credit cards, no subscriptions, and no branding watermarks.

---

## 🚀 Quick Start

### 1. Start the Server

```bash
python server.py
```

### 2. Open in Browser

Visit [http://localhost:8080](http://localhost:8080)

---

## 🛠️ Tech Stack

- **Backend**: Python 3.12, multi-threaded HTTP server, `yt-dlp`, `youtube-transcript-api`, `imageio-ffmpeg`.
- **Frontend**: Vanilla JavaScript (ES6+), HTML5 Canvas 2D engine, MediaRecorder API, CSS3 Glassmorphism with Plus Jakarta Sans & Space Grotesk fonts.
