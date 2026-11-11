try:
    from .youtube_access import youtube_options, extract_youtube_info
except ImportError:
    from youtube_access import youtube_options, extract_youtube_info
try:
    from .clip_boundaries import select_short_clip_windows, snap_to_clean_sentence_boundaries
except ImportError:
    from clip_boundaries import select_short_clip_windows, snap_to_clean_sentence_boundaries

import re
import math
import json
import sys
import os
import urllib.request
import urllib.parse
from youtube_transcript_api import YouTubeTranscriptApi

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

# Viral trigger words and emotional arousal vocabulary
HOOK_KEYWORDS = [
    "secret", "never", "always", "insane", "crazy", "truth", "shocking",
    "stop doing", "why you", "how to", "mistake", "million", "billion",
    "destroy", "money", "ruined", "hack", "algorithm", "formula", "nobody",
    "worst", "best", "biggest", "unbelievable", "revealed", "lie", "warning",
    "listen", "here's why", "don't ever", "if you want", "the real reason"
]

HUMOR_KEYWORDS = [
    "haha", "lol", "lmao", "hilarious", "laugh", "funny", "joke", "prank",
    "dead", "ridiculous", "wild", "awkward", "caught", "screaming", "no way"
]

HIGH_ENERGY_WORDS = [
    "massive", "explosive", "incredible", "genius", "danger", "game changer",
    "viral", "legendary", "super", "epic", "impossible", "holy", "broke"
]

# Streamer microphone commentary & clutch gaming voice markers
STREAMER_KEYWORDS = [
    # Addressing Chat / Viewers
    "chat", "guys", "bhai", "bhai log", "dosto", "doston", "viewers", "stream", "live", "bro", "dude",
    # Gaming Reactions & Clutch Moments
    "no way", "oh my god", "omg", "what the", "what just happened", "are you kidding", "clutch", "headshot",
    "kill", "rush", "revive", "heal", "loot", "zone", "let's go", "lets go", "watch this", "look at",
    "look at my", "one tap", "hacker", "pro", "insane", "literally", "shaking", "clutch god",
    # Hindi / Hinglish Streamer Reactions
    "arre yaar", "bhai bhai", "dekh", "dekho", "dekha", "suno", "ruko", "chalo", "kya mara", "kya clutch",
    "bach gaya", "mar gaya", "kya kar raha hai", "bhot hard", "maza aa gaya", "gadbad", "jaldi", "cover de",
    "revive kar", "rush karo", "op", "bawaal", "khatam", "bacha le", "maro", "ye kya tha", "kya baat hai",
    "record tod diya", "literally kaanp"
]

# In-game scripted narrative / sound tags to suppress so streamer voice is chosen
IN_GAME_GAMEPLAY_BLACKLIST = [
    "mission", "objective", "checkpoint", "level completed", "press e to", "press f to",
    "press space", "loading screen", "system online", "system reboot", "armor depleted",
    "civilian", "sector clear", "commander", "protocol", "tactical reload", "hostile neutralized",
    "game over", "soundtrack", "subtitles by", "press any key", "saving progress"
]

def clean_streamer_text(text: str) -> str:
    """
    Remove in-game sound tags like [Music], [Applause], [Gunfire], (chuckles), ♪, 
    and NPC/radio dialogue prefixes to isolate the streamer's spoken voice.
    """
    if not text:
        return ""
    # Remove bracketed sound effects: [Music], [Sound], [Laughter], (music), (cheering), etc.
    cleaned = re.sub(r'\[.*?\]|\(.*?\)|♪+', ' ', text)
    # Remove in-game character/radio labels: e.g. "Narrator:", "Cop 1:", "Radio:", "NPC:"
    cleaned = re.sub(r'^[A-Za-z0-9_\s]{1,15}:', '', cleaned)
    # Normalize extra whitespaces
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

def extract_youtube_id(url: str) -> str:
    """Extract YouTube video ID from various URL formats including livestreams and shorts."""
    if not url:
        return ""
    url = url.strip()
    
    # Check standard patterns
    patterns = [
        r"(?:v=|\/v\/|embed\/|shorts\/|live\/)([0-9A-Za-z_-]{11})",
        r"youtu\.be\/([0-9A-Za-z_-]{11})",
        r"^([0-9A-Za-z_-]{11})$"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
            
    return ""

def parse_iso8601_duration(duration_str: str) -> float:
    """Parse ISO 8601 duration format (PT1H2M30S) into total seconds."""
    if not duration_str:
        return 600.0
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
    if not match:
        return 600.0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return float(hours * 3600 + minutes * 60 + seconds)

def extract_chapters_from_description(description: str) -> list:
    """Extract chapter timestamps from video description (e.g. 01:23 Topic)."""
    chapters = []
    if not description:
        return chapters
    lines = description.split('\n')
    for line in lines:
        m = re.search(r'(?:(\d{1,2}):)?(\d{1,2}):(\d{2})', line)
        if m:
            hrs = int(m.group(1) or 0)
            mins = int(m.group(2))
            secs = int(m.group(3))
            ts = hrs * 3600 + mins * 60 + secs
            label = re.sub(r'[\(\[\{]?(?:(\d{1,2}):)?(\d{1,2}):(\d{2})[\)\]\}]?', '', line).strip(' -:|•')
            if label:
                chapters.append({"time": ts, "title": label})
    return chapters

def fetch_youtube_data_api(video_id: str, api_key: str = None) -> dict:
    """
    Official YouTube Data API v3 integration:
    Fetches real title, channel, description, duration, thumbnails, and statistics.
    """
    key = api_key or os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not key:
        return None

    try:
        api_url = (
            f"https://www.googleapis.com/youtube/v3/videos?"
            f"part=snippet,contentDetails,statistics&id={video_id}&key={key}"
        )
        req = urllib.request.Request(api_url, headers={'User-Agent': 'godd-ai/1.0'})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            items = data.get("items", [])
            if not items:
                return None

            item = items[0]
            snippet = item.get("snippet", {})
            content = item.get("contentDetails", {})
            stats = item.get("statistics", {})

            # Pick highest resolution thumbnail available
            thumbs = snippet.get("thumbnails", {})
            thumb_url = (
                thumbs.get("maxres", {}).get("url")
                or thumbs.get("standard", {}).get("url")
                or thumbs.get("high", {}).get("url")
                or f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
            )

            dur_sec = parse_iso8601_duration(content.get("duration", ""))
            desc = snippet.get("description", "")
            chapters = extract_chapters_from_description(desc)

            return {
                "title": snippet.get("title", f"YouTube Video ({video_id})"),
                "author": snippet.get("channelTitle", "Creator"),
                "thumbnail": thumb_url,
                "duration": dur_sec,
                "description": desc[:500],
                "view_count": int(stats.get("viewCount", 100000)),
                "like_count": int(stats.get("likeCount", 5000)),
                "chapters": chapters,
                "source": "youtube_data_api_v3"
            }
    except Exception as e:
        print(f"[YouTube Data API] Error fetching video {video_id}: {e}")
        return None

def fetch_oembed_metadata(video_id: str) -> dict:
    """Fallback metadata fetcher using YouTube oEmbed."""
    try:
        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        req = urllib.request.Request(oembed_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return {
                "title": data.get("title", f"YouTube Video ({video_id})"),
                "author": data.get("author_name", "Creator"),
                "thumbnail": f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
                "duration": 600 # Fallback 10 mins
            }
    except Exception:
        return {
            "title": f"Viral Video ({video_id})",
            "author": "Creator",
            "thumbnail": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
            "duration": 600
        }

def get_video_metadata(video_id: str, url: str, api_key: str = None) -> dict:
    """
    Retrieve video metadata.
    Priority 1: Official YouTube Data API v3 (if API key available in payload or YOUTUBE_API_KEY env)
    Priority 2: yt-dlp (if installed)
    Priority 3: YouTube oEmbed fallback
    """
    # 1. Try Official YouTube Data API v3
    official_meta = fetch_youtube_data_api(video_id, api_key)
    if official_meta:
        return official_meta

    # 2. Try yt-dlp if available
    if yt_dlp:
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
                'extract_flat': True
            }
            info = extract_youtube_info(url, ydl_opts)
            return {
                "title": info.get("title", f"Video {video_id}"),
                "author": info.get("uploader", info.get("channel", "Creator")),
                "thumbnail": info.get("thumbnail") or f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
                "duration": info.get("duration", 600),
                "description": (info.get("description") or "")[:300],
                "view_count": info.get("view_count", 150000)
            }
        except Exception as e:
            print(f"[Metadata] yt-dlp warning: {e}, falling back to oEmbed")

    # 3. Fast oEmbed fallback
    meta = fetch_oembed_metadata(video_id)
    return meta

def fetch_transcript_from_ytdlp(video_id: str, video_url: str = None) -> list:
    """
    Fetch real timed text subtitles directly from YouTube timedtext API via yt-dlp.
    Extracts the exact spoken words with millisecond timestamps.
    """
    if not yt_dlp:
        return []
    url = video_url or f"https://www.youtube.com/watch?v={video_id}"
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
        }
        info = extract_youtube_info(url, ydl_opts)
        subs = info.get('subtitles') or {}
        auto_subs = info.get('automatic_captions') or {}

        # Prioritize Hindi/Hinglish, then Indian English, then English
        chosen_sub_formats = None
        for lang in ['hi', 'hi-Latn', 'en-IN', 'en', 'en-US', 'en-GB']:
            if lang in subs:
                chosen_sub_formats = subs[lang]
                break
            if lang in auto_subs:
                chosen_sub_formats = auto_subs[lang]
                break

        if not chosen_sub_formats:
            if subs:
                chosen_sub_formats = next(iter(subs.values()))
            elif auto_subs:
                chosen_sub_formats = next(iter(auto_subs.values()))

        if not chosen_sub_formats:
            return []

        # Prefer json3 format for millisecond-level word timing
        json3_url = next((f['url'] for f in chosen_sub_formats if f.get('ext') == 'json3'), None)
        if not json3_url:
            json3_url = chosen_sub_formats[0].get('url')

        if not json3_url:
            return []

        req = urllib.request.Request(json3_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            events = data.get('events', [])
            results = []
            for ev in events:
                start_sec = ev.get('tStartMs', 0) / 1000.0
                dur_sec = ev.get('dDurationMs', 0) / 1000.0
                segs = ev.get('segs', [])
                text = "".join(s.get('utf8', '') for s in segs).replace("\n", " ").strip()
                cleaned = clean_streamer_text(text)
                if cleaned and len(cleaned) > 1:
                    results.append({
                        "text": cleaned,
                        "start": round(start_sec, 2),
                        "duration": round(dur_sec, 2),
                        "end": round(start_sec + dur_sec, 2)
                    })
            return results
    except Exception as e:
        print(f"[yt-dlp Captions] Notice: {e}")
        return []

def fetch_transcript_segments(video_id: str, url: str = None) -> list:
    """
    Fetch REAL transcripts spoken in the video:
    1. Try YouTubeTranscriptApi (manual creator tracks & auto-generated tracks)
    2. Try yt-dlp direct timedtext extractor (bypasses blocks via mobile client)
    """
    results = []

    # Method 1: YouTubeTranscriptApi
    try:
        api = YouTubeTranscriptApi()
        try:
            t_list = api.list(video_id)
            transcript_data = None
            for preferred in [['hi', 'hi-Latn', 'en-IN', 'en', 'en-US'], ['hi', 'hi-Latn', 'en-IN'], ['en', 'en-US']]:
                try:
                    t = t_list.find_manually_created_transcript(preferred)
                    transcript_data = t.fetch()
                    break
                except Exception:
                    pass
                try:
                    t = t_list.find_generated_transcript(preferred)
                    transcript_data = t.fetch()
                    break
                except Exception:
                    pass
            if not transcript_data:
                for t in t_list:
                    try:
                        transcript_data = t.fetch()
                        break
                    except Exception:
                        pass
        except Exception:
            try:
                transcript_data = api.fetch(video_id, languages=['hi', 'hi-Latn', 'en-IN', 'en'])
            except Exception:
                try:
                    transcript_data = api.fetch(video_id)
                except Exception:
                    transcript_data = None

        if transcript_data:
            for item in transcript_data:
                raw_text = item.text.replace("\n", " ").strip()
                cleaned_text = clean_streamer_text(raw_text)
                if cleaned_text and len(cleaned_text) > 1:
                    results.append({
                        "text": cleaned_text,
                        "start": float(item.start),
                        "duration": float(item.duration),
                        "end": float(item.start) + float(item.duration)
                    })
    except Exception as e:
        print(f"[Transcript API] Notice: {e}")

    # Method 2: If YouTubeTranscriptApi returned 0 or < 5 segments, use yt-dlp timedtext
    if len(results) < 5:
        print(f"[Transcript] Trying yt-dlp timedtext extraction for {video_id}...")
        ytdlp_segments = fetch_transcript_from_ytdlp(video_id, url)
        if len(ytdlp_segments) > len(results):
            results = ytdlp_segments

    print(f"[Transcript] Total real spoken segments extracted: {len(results)}")
    return results

def generate_word_subtitles(start_sec: float, end_sec: float, text: str) -> list:
    """Generate fine-grained word timings for animated karaoke subtitles."""
    words = [w.strip() for w in text.split() if w.strip()]
    if not words:
        return []
        
    total_duration = max(0.5, end_sec - start_sec)
    time_per_word = total_duration / len(words)
    
    subtitles = []
    current_time = start_sec
    for i, word in enumerate(words):
        duration = time_per_word
        # Give slightly longer pause to commas/periods
        if word.endswith((".", "!", "?")):
            duration *= 1.3
        elif word.endswith(","):
            duration *= 1.15
            
        w_end = min(end_sec, current_time + duration)
        
        # Detect highlight emphasis and emojis
        is_highlight = any(k in word.lower() for k in HOOK_KEYWORDS + HIGH_ENERGY_WORDS)
        emoji = ""
        lower_word = word.lower()
        if "money" in lower_word or "million" in lower_word or "billion" in lower_word or "dollar" in lower_word:
            emoji = " 💰"
        elif "crazy" in lower_word or "insane" in lower_word or "shock" in lower_word or "mind" in lower_word:
            emoji = " 🤯"
        elif "fire" in lower_word or "hot" in lower_word or "game" in lower_word:
            emoji = " 🔥"
        elif "rocket" in lower_word or "viral" in lower_word or "growth" in lower_word:
            emoji = " 🚀"
        elif "secret" in lower_word or "hack" in lower_word or "key" in lower_word:
            emoji = " 💡"
            
        subtitles.append({
            "word": word + emoji,
            "start": round(current_time, 2),
            "end": round(w_end, 2),
            "highlight": is_highlight
        })
        current_time = w_end
        
    return subtitles

def analyze_virality_and_cut_clips(transcript: list, video_duration: float, title: str) -> list:
    """
    AI Virality Detection Engine:
    Identifies high-retention 30-60 second clips using:
    - First 3-second hook strength
    - Sentiment and emotional arousal keywords
    - Speech density (WPM)
    - Pacing and climax conclusion
    """
    if not transcript:
        return []
        
    short_windows = select_short_clip_windows(transcript, video_duration)
    windows = short_windows or (
        snap_to_clean_sentence_boundaries(transcript, float(seg["start"]), boundary_limit=video_duration)
        for seg in transcript[::max(1, len(transcript) // 25)]
        if float(seg["start"]) + 35.0 <= video_duration
    )
    candidate_windows = []
    for start_time, end_time, segments in windows:
        if not segments:
            continue
        current_words = [seg.get("text", "") for seg in segments]
        full_text = " ".join(current_words)
        score, reasons, tags, hook_text = score_segment(
            start_time, end_time - start_time, full_text, " ".join(current_words[:4]))
        candidate_windows.append({
            "start": start_time, "end": end_time, "duration_sec": round(end_time - start_time, 2),
            "text": full_text, "score": score, "reasons": reasons, "tags": tags, "hook": hook_text})

    if not short_windows:
        candidate_windows.sort(key=lambda x: x["score"], reverse=True)
    
    # Filter out overlapping windows to give distinct, diverse viral moments
    selected_clips = []
    for cand in candidate_windows:
        overlap = False
        for s in selected_clips:
            # Check if overlapping by more than 10 seconds
            if not (cand["end"] < s["start"] + 5 or cand["start"] > s["end"] - 5):
                overlap = True
                break
        if not overlap:
            selected_clips.append(cand)
            if len(selected_clips) >= 5: # Top 5 viral clips
                break
                
    if not selected_clips:
        return []
        
    # Format selected clips for Klap-style display
    formatted = []
    for idx, clip in enumerate(selected_clips):
        words = clip["text"].split()
        subtitles = generate_word_subtitles(clip["start"], clip["end"], clip["text"])
        
        # Generate punchy short title
        viral_title = generate_viral_title(clip["hook"], clip["tags"], idx + 1)
        
        formatted.append({
            "id": f"clip_{idx+1}",
            "rank": idx + 1,
            "title": viral_title,
            "hook": clip["hook"],
            "start": clip["start"],
            "end": clip["end"],
            "duration": format_duration(clip["duration_sec"]),
            "duration_sec": clip["duration_sec"],
            "virality_score": clip["score"],
            "virality_badge": "🔥 Viral Hit" if clip["score"] >= 92 else "⚡ High Potential",
            "viral_reasons": clip["reasons"],
            "tags": clip["tags"],
            "full_text": clip["text"],
            "subtitles": subtitles,
            "has_real_captions": True
        })
        
    return formatted

def score_segment(start_time: float, duration: float, text: str, first_phrase: str) -> tuple:
    """Calculate 0-100 Virality Score prioritizing streamer microphone commentary over in-game narrative."""
    lower_text = text.lower()
    lower_hook = first_phrase.lower()
    
    score = 70.0 # Base score
    reasons = []
    tags = []
    
    # 1. STREAMER MIC VOICE PRIORITY (Massive Boost for Streamer Commentary)
    streamer_matches = [w for w in STREAMER_KEYWORDS if w in lower_text or w in lower_hook]
    if streamer_matches:
        score += 25.0
        reasons.append(f"Streamer mic commentary & live reaction ('{streamer_matches[0]}')")
        tags.append("Streamer Voice")
        tags.append("Live Clutch")
    
    # 2. IN-GAME SCRIPTED NARRATIVE SUPPRESSION
    in_game_matches = [w for w in IN_GAME_GAMEPLAY_BLACKLIST if w in lower_text]
    if in_game_matches and not streamer_matches:
        score -= 28.0 # Heavily deprioritize in-game NPC/cutscene dialogue
    
    # 3. Hook Strength in first 3-5 seconds
    hook_matches = [w for w in HOOK_KEYWORDS if w in lower_hook]
    if hook_matches:
        score += 12.0
        reasons.append(f"Instant curiosity hook: '{hook_matches[0]}'")
        if "Strong Hook" not in tags:
            tags.append("Strong Hook")
    elif any(char in lower_hook for char in ["?", "!"]):
        score += 7.0
        reasons.append("Opening reaction creates curiosity")
        if "Curiosity Loop" not in tags:
            tags.append("Curiosity Loop")
    else:
        score += 3.0
        
    # 4. Emotional and High Energy keywords
    energy_matches = [w for w in HIGH_ENERGY_WORDS if w in lower_text]
    if energy_matches:
        score += 8.0
        reasons.append(f"High energy reaction ('{energy_matches[0]}')")
        tags.append("High Energy")
        
    # 5. Humor / Entertainment triggers
    humor_matches = [w for w in HUMOR_KEYWORDS if w in lower_text]
    if humor_matches:
        score += 6.0
        reasons.append("Spontaneous humor & banter")
        tags.append("Entertaining")
        
    # 6. Pacing & Speech Density (Words Per Minute)
    word_count = len(text.split())
    wpm = (word_count / max(1.0, duration)) * 60
    if 130 <= wpm <= 190:
        score += 5.0
        reasons.append(f"Punchy streamer pacing ({int(wpm)} WPM)")
    elif wpm > 190:
        score += 3.0
        reasons.append("Fast-paced live callouts")
    else:
        score += 1.0
        
    # 7. Optimal Shorts/Reels duration (30s - 45s)
    if 30 <= duration <= 50:
        score += 4.0
        tags.append("Algorithm Pick")
        
    final_score = max(50, min(99, int(round(score))))
    
    # Extract concise hook
    clean_hook = first_phrase.strip().capitalize()
    if len(clean_hook) > 60:
        clean_hook = clean_hook[:57] + "..."
        
    if not tags:
        tags = ["Streamer Voice", "Highlight"]
        
    return final_score, reasons[:3], tags[:3], clean_hook

def generate_viral_title(hook: str, tags: list, rank: int) -> str:
    """Generate high-CTR TikTok/Reels headline in Hinglish focusing on streamer commentary."""
    emojis = ["🤯", "🔥", "🚀", "😱", "⚠️", "⚡"]
    emoji = emojis[(rank - 1) % len(emojis)]
    
    clean_hook = hook.replace('"', '').replace("'", '').strip()
    if len(clean_hook) > 40:
        words = clean_hook.split()[:6]
        clean_hook = " ".join(words)
        
    templates = [
        f"Bhai Yeh Kya Clutch Tha {emoji}",
        f"Chat Dekho Yeh Kya Ho Gaya {emoji}",
        f"{clean_hook}... End Tak Ruk Jaa {emoji}",
        f"Streamer Reaction: Record Tod Diya {emoji}",
        f"Yaar Tu Believe Nahi Karega {emoji}"
    ]
    return templates[(rank - 1) % len(templates)]

def format_duration(seconds: float) -> str:
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}:{secs:02d}"

def synthesize_viral_clips(video_duration: float, title: str) -> list:
    """
    Intelligent timestamp cutting when YouTube auto-captions are not available.
    Cuts high-potential segments across the video based on duration without fabricating fake text.
    """
    video_dur = max(60.0, float(video_duration))
    clean_title = re.sub(r'[^\w\s-]', '', title).strip() or "Live Stream Highlight"
    short_title = clean_title[:32]
    
    # 4 high-retention windows across the video
    intervals = [
        {"offset": 0.08, "dur": 35.0, "rank": 1, "score": 98, "tag": "Opening Hook"},
        {"offset": 0.32, "dur": 38.0, "rank": 2, "score": 95, "tag": "Peak Action"},
        {"offset": 0.58, "dur": 40.0, "rank": 3, "score": 92, "tag": "Climax Moment"},
        {"offset": 0.80, "dur": 32.0, "rank": 4, "score": 89, "tag": "Highlight Finale"}
    ]
    
    formatted = []
    for item in intervals:
        start_time = round(video_dur * item["offset"], 1)
        end_time = round(min(video_dur - 1, start_time + item["dur"]), 1)
        actual_dur = round(end_time - start_time, 1)
        
        clip_title = f"{short_title} - Clip #{item['rank']} 🔥"
        hook_text = f"Highlight from {short_title}"
        subtitle_text = f"{short_title} live highlight. Type or edit streamer words here!"
        
        subtitles = generate_word_subtitles(start_time, end_time, subtitle_text)
        
        formatted.append({
            "id": f"clip_{item['rank']}",
            "rank": item["rank"],
            "title": clip_title,
            "hook": hook_text,
            "start": start_time,
            "end": end_time,
            "duration": format_duration(actual_dur),
            "duration_sec": actual_dur,
            "virality_score": item["score"],
            "virality_badge": "🔥 Viral Hit" if item["score"] >= 92 else "⚡ High Potential",
            "viral_reasons": ["High engagement window", f"Paced {actual_dur}s short duration"],
            "tags": [item["tag"], "Short"],
            "full_text": subtitle_text,
            "subtitles": subtitles,
            "has_real_captions": False
        })
        
    return formatted
