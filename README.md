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


## Clip subtitles and audio

Install dependencies with `python -m pip install -r requirements.txt`, then run
`python server.py`. FFmpeg must support the `subtitles` filter (the Docker image
and bundled imageio-ffmpeg build do). On Linux, install a font covering the spoken
language; the Docker image includes Latin and Devanagari fonts.

Exports burn in available source captions. If none are supplied, faster-whisper
transcribes the selected export audio with automatic language detection and word
timestamps. Its first use downloads the `small` multilingual model and may take longer; set
`WHISPER_MODEL=tiny` for lower memory use. Missing recognition dependencies or
subtitle rendering errors are reported instead of silently exporting without
requested captions. Select subtitles **Off** to disable captions.

Each MP4 contains one selected audio stream, preferring a rendition marked
original over a dubbed track. Audio and video seek to the same clip start; audio
resampling corrects timestamp drift. Captions and SRT exports use clip-relative
timing without an automatic lead. This prevents extra-track duplication; voices
or echoes already mixed into a single source track require separate audio
restoration. Existing lip-sync errors in the source are not automatically inferred.


## Complete answer boundaries

Clip selection treats 58 seconds as a target and 85 seconds as a soft limit.
It can extend up to 180 seconds when transcript pauses, conclusions, or a next
question indicate a stronger ending. It rejects open clauses and question-only
endings, and keeps tail padding outside the next utterance. Creator chapter
boundaries and the video end constrain the search. Candidates without a usable
ending are skipped rather than forced into a duration window.

This uses transcript heuristics, not a semantic model of the complete answer.
Unpunctuated speech, long multi-part answers, or an unavailable transcript still
need review. Suggested ranges without a transcript are identified in the UI;
connection failures no longer silently create placeholder clips. Manual trim
changes are honored by the downloaded file as well as the preview.


## YouTube download access

Install `yt-dlp[default]` from requirements and Node.js 22+ (Node 24 is bundled
in the Docker image). The app enables Node and the matching EJS package for
YouTube extraction. A YouTube rate limit or sign-in block is reported before
rendering; subtitle changes cannot resolve it.

For a local authenticated session, explicitly set `YOUTUBE_COOKIE_BROWSER=chrome`
before launching the server. Chrome's Windows encryption can prevent yt-dlp
from reading its cookies. Alternatively, set `YOUTUBE_COOKIE_FILE` to the absolute
path of a YouTube-only Netscape cookies file kept on your computer. Do not share
that file, paste it into chat, or commit it. Cookie files take precedence over
browser extraction. Authentication may still be rate limited by YouTube.


### Local server and request reuse

Only one local server may own the listening port on Windows. Stop the existing
server before restarting after backend changes; `/healthz` reports the active
backend version and caption renderer. This prevents a new frontend from calling
an older renderer that is still running in memory.

YouTube extraction results are shared for five minutes between metadata,
transcript, and export requests, including equivalent `youtu.be` and watch URLs.
After a YouTube access block, the app pauses equivalent extraction attempts for
one minute instead of immediately repeating them through every fallback.


## Speech-matched export captions

Automatic exports now render the selected video/audio clip first, recognize its
actual local audio, then burn styled captions while copying that audio unchanged.
This gives recognition and output the same zero-based clock. Estimated preview
words and translated source tracks are not used as automatic export captions.
The default recognition model is multilingual `small`; `WHISPER_LANGUAGE` may
optionally force a spoken language, otherwise detection is automatic. Recognition
uses transcription, not translation. Larger models take longer on CPU.

The downloaded clip's measured words are returned to the site preview and SRT
export. Original timed words retain their real endpoints; preview phrases no
longer persist through artificial hold intervals. Speech recognition can still
make mistakes, especially with overlapping speakers, accents, and mixed languages.


## Public Render deployment (free demo)

The `render.yaml` Blueprint deploys the Docker service on Render Free. It serves
the site and API from the same public domain. Deploy from the `main` branch of
`https://github.com/WhiffGodd/godd-ai` using Render's Docker runtime and health
check `/healthz`. The deployed health version is `1.3.0`.

The free profile uses multilingual Whisper `base`, one CPU thread and one export
at a time. This uses less memory than the local `small` model, with a tradeoff in
recognition accuracy. Exports run as bounded background jobs; the browser polls
status instead of holding a render request open. Temporary results expire after
30 minutes and are lost on restart. The speech model and Node runtime are bundled
in the image. Local videos, browser cookies and `.env` files are excluded.

Render Free sleeps on idle, has limited memory/CPU, and is suitable for a public
demo rather than dependable production rendering. YouTube can also block cloud
hosting IPs. A successful web deployment does not guarantee access to every
YouTube video. Personal browser cookies are never included in deployment.

To publish: connect Render, select the existing `godd-ai` service and deploy the
latest `main` commit, or create a Blueprint from the repository. Keep the Free
instance selected. Share the service's assigned HTTPS URL after `/healthz` shows
version `1.3.0` and a browser export has been verified.


### YouTube playback verification on Render

The image includes bgutil-ytdlp-pot-provider 2.0.2 and its matching Node script,
as recommended in yt-dlp's PO Token Guide. It runs on demand during extraction,
then exits before encoding and speech recognition. Mobile-web, Safari and
embedded playback clients are configured, and FFmpeg preserves the selected
stream's HTTP playback headers. No personal account cookies are bundled.

Playback verification can improve access but cannot guarantee access from a
blocked datacenter IP or to a video requiring sign-in. Treat a download as
verified only after the affected video's export succeeds on the deployed host.


### Blocked-video upload alternative

When YouTube blocks an export, the error dialog offers **Upload original video
and retry**. Choose the same original video (up to 1 GB). Uploads use 4 MB chunks
and stream to temporary storage; the visitor does not need a local backend.
The selected start/end, layout and subtitle style stay the same. Rendering reads
that uploaded source directly and recognizes its clip audio without contacting
YouTube. Uploads are identified by random tokens, expire after one hour, and
are lost if the free service restarts. Only use videos you are allowed to upload.
This is an alternative source path, not a claim that YouTube's IP block is removed.
