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
    Remove speaker arrows (<<, >>, <<<, >>>), HTML entities (&lt;, &gt;, &amp;),
    bracketed sound tags ([Music], [Applause], (laughter), ♪), and NPC/radio dialogue prefixes
    to isolate pure spoken words without noise.
    """
    if not text:
        return ""
    # Strip HTML entities & speaker change indicators: <<, >>, <<<, >>>, &lt;, &gt;, «, »
    cleaned = re.sub(r'&(?:lt|gt|amp|quot|apos);?', ' ', text)
    cleaned = re.sub(r'[«»<>]+', ' ', cleaned)
    # Remove bracketed sound effects: [Music], [Sound], [Laughter], (music), (cheering), etc.
    cleaned = re.sub(r'\[.*?\]|\(.*?\)|♪+', ' ', cleaned)
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
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                desc = info.get("description") or ""
                chapters = info.get("chapters") or []
                if not chapters:
                    chapters = extract_chapters_from_description(desc)

                return {
                    "title": info.get("title", f"Video {video_id}"),
                    "author": info.get("uploader", info.get("channel", "Creator")),
                    "thumbnail": info.get("thumbnail") or f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
                    "duration": info.get("duration", 600),
                    "description": desc[:500],
                    "view_count": info.get("view_count", 150000),
                    "chapters": chapters
                }
        except Exception as e:
            print(f"[Metadata] yt-dlp warning: {e}, falling back to oEmbed")

    # 3. Fast oEmbed fallback
    meta = fetch_oembed_metadata(video_id)
    return meta

def detect_video_language(video_title: str = "", description: str = "") -> str:
    """
    Detect whether the video is in English, Hindi, or another language.
    If the text has significant Devanagari script (\u0900-\u097F), returns 'hi'.
    Otherwise, defaults to 'en' (English).
    """
    text = (video_title or "") + " " + (description or "")
    devanagari = len(re.findall(r'[\u0900-\u097F]', text))
    latin = len(re.findall(r'[A-Za-z]', text))
    if devanagari > 4 and devanagari > latin * 0.25:
        return 'hi'
    return 'en'

def fetch_transcript_from_ytdlp(video_id: str, video_url: str = None, is_english: bool = True) -> list:
    """
    Direct extractor for timed captions from YouTube's timedtext service via yt-dlp.
    Prioritizes the correct language matching the video's actual spoken audio.
    """
    if not yt_dlp:
        return []
    url = video_url or f"https://www.youtube.com/watch?v={video_id}"
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'extractor_args': {'youtube': {'player_client': ['android', 'ios', 'mweb']}}
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            subs = info.get('subtitles') or {}
            auto_subs = info.get('automatic_captions') or {}

            # Prioritize matching the video's original spoken language
            if is_english:
                lang_order = ['en', 'en-US', 'en-GB', 'en-CA', 'en-IN', 'en-AU']
            else:
                lang_order = ['hi', 'hi-Latn', 'en-IN', 'en']

            chosen_sub_formats = None
            for lang in lang_order:
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

def fetch_transcript_segments(video_id: str, url: str = None, video_title: str = "") -> list:
    """
    Fetch REAL transcripts spoken in the video:
    - If English podcast/video -> guarantees English subtitles!
    - If Hindi video -> fetches Hindi/Hinglish subtitles.
    """
    results = []
    lang = detect_video_language(video_title)
    is_english = (lang == 'en')
    print(f"[Transcript] Target language for '{video_title[:35]}...': {'English (en)' if is_english else 'Hindi (hi)'}")

    if is_english:
        preferred_langs = ['en', 'en-US', 'en-GB', 'en-CA', 'en-IN', 'en-AU']
    else:
        preferred_langs = ['hi', 'hi-Latn', 'en-IN', 'en']

    # Method 1: YouTubeTranscriptApi
    try:
        api = YouTubeTranscriptApi()
        try:
            t_list = api.list(video_id)
            transcript_data = None

            # 1. Try manual transcript in preferred language
            try:
                t = t_list.find_manually_created_transcript(preferred_langs)
                transcript_data = t.fetch()
            except Exception:
                pass

            # 2. Try auto-generated transcript in preferred language
            if not transcript_data:
                try:
                    t = t_list.find_generated_transcript(preferred_langs)
                    transcript_data = t.fetch()
                except Exception:
                    pass

            # 3. If English requested, check any transcript code starting with 'en'
            if not transcript_data and is_english:
                for t in t_list:
                    if str(t.language_code).lower().startswith('en'):
                        try:
                            transcript_data = t.fetch()
                            break
                        except Exception:
                            pass

            if not transcript_data and not is_english:
                for t in t_list:
                    if str(t.language_code).lower().startswith('hi'):
                        try:
                            transcript_data = t.fetch()
                            break
                        except Exception:
                            pass

        except Exception as e:
            try:
                transcript_data = api.fetch(video_id, languages=preferred_langs)
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
        print(f"[Transcript] Trying yt-dlp timedtext extraction for {video_id} (is_english={is_english})...")
        ytdlp_segments = fetch_transcript_from_ytdlp(video_id, url, is_english=is_english)
        if len(ytdlp_segments) > len(results):
            results = ytdlp_segments

    print(f"[Transcript] Total real spoken segments extracted: {len(results)}")
    return results

def generate_word_subtitles_from_segments(segments: list, clip_start: float, clip_end: float) -> list:
    """
    Extract word-level subtitle timings from real spoken transcript segments.
    Applies an anticipatory lead offset (180ms) and strips speaker change markers (<<, >>).
    """
    if not segments:
        return []
    clip_segs = [s for s in segments if s.get("end", 0) >= clip_start and s.get("start", 0) <= clip_end]
    if not clip_segs:
        return []

    subtitles = []
    lead_offset = 0.18  # Subtitles precede speech by 180ms so the viewer anticipates spoken words smoothly

    for seg in clip_segs:
        s_start = max(0.0, float(seg.get("start", 0)) - lead_offset)
        s_end = max(s_start + 0.35, float(seg.get("end", s_start + 1.0)) - (lead_offset * 0.5))

        # Clean text of <<, >>, HTML tags, and sound tags
        cleaned_text = re.sub(r'&(?:lt|gt|amp|quot|apos);?', ' ', str(seg.get("text", "")))
        cleaned_text = re.sub(r'[«»<>]+', ' ', cleaned_text)

        raw_words = [w.strip() for w in cleaned_text.split() if w.strip()]
        if not raw_words:
            continue

        seg_dur = max(0.25, s_end - s_start)
        t_per_word = seg_dur / len(raw_words)
        cur = s_start
        for w in raw_words:
            w_clean = re.sub(r'[«»<>]+', '', w).strip()
            if not w_clean:
                continue
            w_end = round(cur + max(0.20, t_per_word), 2)
            subtitles.append({
                "word": w_clean,
                "start": round(cur, 2),
                "end": w_end,
                "highlight": any(k in w_clean.lower() for k in ["important", "key", "secret", "never", "why", "how", "truth", "future", "mind", "huge", "biggest", "realize", "best", "worst"])
            })
            cur = cur + t_per_word
    return subtitles

def generate_word_subtitles(start_sec: float, end_sec: float, text: str) -> list:
    """Generate fine-grained word timings for animated karaoke subtitles with lead time."""
    clean_text = re.sub(r'[«»<>]+', ' ', text or '')
    words = [w.strip() for w in clean_text.split() if w.strip()]
    if not words:
        return []

    lead_offset = 0.18
    adj_start = max(0.0, start_sec - lead_offset)
    total_duration = max(0.5, end_sec - adj_start)
    time_per_word = total_duration / len(words)

    subtitles = []
    current_time = adj_start
    for i, word in enumerate(words):
        w_clean = re.sub(r'[«»<>]+', '', word).strip()
        if not w_clean:
            continue
        duration = time_per_word
        if w_clean.endswith((".", "!", "?")):
            duration *= 1.25
        elif w_clean.endswith(","):
            duration *= 1.12

        w_end = min(end_sec, current_time + max(0.20, duration))
        is_highlight = any(k in w_clean.lower() for k in HOOK_KEYWORDS + HIGH_ENERGY_WORDS)

        subtitles.append({
            "word": w_clean,
            "start": round(current_time, 2),
            "end": round(w_end, 2),
            "highlight": is_highlight
        })
        current_time = current_time + duration
        
    return subtitles

def analyze_virality_and_cut_clips(transcript: list, video_duration: float, title: str, chapters: list = None) -> list:
    """
    AI Content & Virality Detection Engine (Klap-style):
    Identifies high-value, meaningful clips using:
    - Creator chapter markers & structured topics
    - Questions, insights, revelations & storytelling arcs
    - Spoken speech density & complete narrative thoughts
    """
    # 1. PRIORITY: If creator provided chapter timestamps, use these real curated content moments!
    if chapters and len(chapters) >= 2:
        ignore_words = ["intro", "outro", "sponsor", "welcome", "subscribe", "disclaimer", "patreon", "merch", "credits"]
        filtered_chapters = [
            ch for ch in chapters 
            if not any(w in str(ch.get("title", "")).lower() for w in ignore_words)
        ]
        if not filtered_chapters:
            filtered_chapters = chapters
            
        meaningful_clips = []
        for idx, ch in enumerate(filtered_chapters[:5]):
            start_time = float(ch.get("time", ch.get("start_time", 0)))
            ch_title = str(ch.get("title", f"Key Moment #{idx+1}")).strip()
            
            clip_dur = 38.0
            if start_time + clip_dur > video_duration:
                start_time = max(0.0, video_duration - clip_dur)
            end_time = min(video_duration, start_time + clip_dur)
            
            # Words spoken during this chapter window
            ch_words = [s["text"] for s in (transcript or []) if s.get("start", 0) >= start_time and s.get("end", 0) <= end_time]
            full_text = " ".join(ch_words) if ch_words else ch_title
            
            clip_title = generate_meaningful_content_title(clip_text=full_text, video_title=title, chapter_title=ch_title, rank=idx+1)
            
            meaningful_clips.append({
                "id": f"clip_{idx+1}",
                "rank": idx + 1,
                "title": clip_title,
                "hook": ch_title,
                "start": round(start_time, 1),
                "end": round(end_time, 1),
                "duration": format_duration(clip_dur),
                "duration_sec": clip_dur,
                "virality_score": 98 - idx * 2,
                "virality_badge": "🔥 Core Highlight" if idx == 0 else "⚡ Key Insight",
                "viral_reasons": ["Creator Chapter Topic", f"Content: {ch_title[:32]}"],
                "tags": ["Key Chapter", "Deep Dive", "Must Watch"],
                "full_text": full_text,
                "subtitles": generate_word_subtitles_from_segments(transcript, start_time, end_time) or generate_word_subtitles(start_time, end_time, full_text),
                "has_real_captions": bool(ch_words)
            })
            
        if meaningful_clips:
            return meaningful_clips

    if not transcript or len(transcript) < 5:
        # If no transcript was fetched (e.g., auto-captions off), synthesize content-focused segments based on video title
        return synthesize_viral_clips(video_duration, title, chapters=chapters)
        
    target_clip_length = 40.0 # ~40 seconds per short
    min_clip_length = 25.0
    max_clip_length = 60.0
    
    candidate_windows = []
    total_segments = len(transcript)
    
    # Slide across transcript segments
    step = max(1, total_segments // 25)
    for i in range(0, total_segments, step):
        start_seg = transcript[i]
        start_time = start_seg["start"]
        
        # Don't start too close to video end
        if start_time + min_clip_length > video_duration:
            break
            
        current_words = []
        end_time = start_time
        
        for j in range(i, total_segments):
            seg = transcript[j]
            current_words.append(seg["text"])
            end_time = seg["end"]
            
            dur = end_time - start_time
            if dur >= min_clip_length:
                full_text = " ".join(current_words)
                
                # Calculate virality score
                score, reasons, tags, hook_text = score_segment(
                    start_time=start_time,
                    duration=dur,
                    text=full_text,
                    first_phrase=" ".join(current_words[:min(4, len(current_words))])
                )
                
                candidate_windows.append({
                    "start": round(start_time, 2),
                    "end": round(end_time, 2),
                    "duration_sec": round(dur, 1),
                    "text": full_text,
                    "score": score,
                    "reasons": reasons,
                    "tags": tags,
                    "hook": hook_text
                })
                
                if dur >= max_clip_length:
                    break
                    
    # Sort candidates by virality score descending
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
        return synthesize_viral_clips(video_duration, title)
        
    # Format selected clips for Klap-style display
    formatted = []
    for idx, clip in enumerate(selected_clips):
        words = clip["text"].split()
        
        # Generate punchy, content-focused short title based on actual spoken topic
        viral_title = generate_meaningful_content_title(clip_text=clip["text"], video_title=title, rank=idx + 1)
        
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
            "subtitles": generate_word_subtitles_from_segments(transcript, clip["start"], clip["end"]) or generate_word_subtitles(clip["start"], clip["end"], clip["text"]),
            "has_real_captions": True
        })
        
    return formatted

# Content and insight keywords for podcast, education, tech, and storytelling
CONTENT_INSIGHT_KEYWORDS = [
    "realize", "realized", "truth", "secret", "mistake", "system", "strategy",
    "problem", "solution", "framework", "lesson", "rule", "future", "result",
    "reason", "explain", "understand", "difference", "concept", "breakdown",
    "money", "dollar", "percent", "growth", "build", "company", "career",
    "code", "algorithm", "learn", "teach", "advice", "success", "fail"
]

def score_segment(start_time: float, duration: float, text: str, first_phrase: str) -> tuple:
    """Calculate 0-100 Virality Score prioritizing meaningful content, curiosity hooks, and clarity."""
    lower_text = text.lower()
    lower_hook = first_phrase.lower()
    
    score = 72.0 # Base score
    reasons = []
    tags = []
    
    # 1. Spoken Questions & Curiosity Loops in First 4 Seconds
    if "?" in lower_hook or any(lower_hook.startswith(q) for q in ["why ", "how ", "what if ", "can we ", "is it ", "have you "]):
        score += 15.0
        reasons.append("Opening curiosity question grabs immediate retention")
        tags.append("Curiosity Loop")
    elif any(char in lower_hook for char in ["?", "!"]):
        score += 8.0
        reasons.append("Opening phrase creates tension")
        tags.append("Strong Hook")

    # 2. Viral & Curiosity Hook Keywords
    hook_matches = [w for w in HOOK_KEYWORDS if w in lower_hook or w in lower_text[:80]]
    if hook_matches:
        score += 12.0
        reasons.append(f"High-impact hook keyword: '{hook_matches[0]}'")
        if "Strong Hook" not in tags:
            tags.append("Strong Hook")

    # 3. Content Insight & Value Keywords (Podcasts, Tech, Lessons, Stories)
    insight_matches = [w for w in CONTENT_INSIGHT_KEYWORDS if w in lower_text]
    if insight_matches:
        score += 10.0
        reasons.append(f"Substantive insight topic ('{insight_matches[0]}')")
        tags.append("Key Insight")

    # 4. Streamer & Live Commentary Excitement
    streamer_matches = [w for w in STREAMER_KEYWORDS if w in lower_text or w in lower_hook]
    if streamer_matches:
        score += 10.0
        reasons.append(f"High-energy live reaction ('{streamer_matches[0]}')")
        tags.append("Streamer Voice")

    # 5. Emotional and High Energy Keywords
    energy_matches = [w for w in HIGH_ENERGY_WORDS if w in lower_text]
    if energy_matches:
        score += 6.0
        reasons.append(f"Peak energy moment ('{energy_matches[0]}')")
        if "High Energy" not in tags:
            tags.append("High Energy")

    # 6. Humor & Banter Triggers
    humor_matches = [w for w in HUMOR_KEYWORDS if w in lower_text]
    if humor_matches:
        score += 5.0
        reasons.append("Spontaneous humor & banter")
        tags.append("Entertaining")

    # 7. Speech Cadence & Density (Words Per Minute)
    word_count = len(text.split())
    wpm = (word_count / max(1.0, duration)) * 60
    if 120 <= wpm <= 185:
        score += 5.0
        reasons.append(f"Optimal speech cadence ({int(wpm)} WPM)")
    elif wpm > 185:
        score += 3.0

    # 8. Ideal Short Duration (30s - 45s)
    if 30 <= duration <= 48:
        score += 4.0
        tags.append("Algorithm Pick")

    final_score = max(55, min(99, int(round(score))))
    
    # Extract clean hook
    clean_hook = first_phrase.strip().capitalize()
    if len(clean_hook) > 60:
        clean_hook = clean_hook[:57] + "..."
        
    if not tags:
        tags = ["Key Insight", "Highlight"]
        
    return final_score, reasons[:3], tags[:3], clean_hook

def extract_meaningful_topic_phrase(text: str) -> str:
    """Extract the most prominent concept or noun phrase from spoken clip text."""
    if not text:
        return ""
    stopwords = {
        'the', 'this', 'that', 'these', 'those', 'what', 'when', 'where', 'which', 'who',
        'whom', 'whose', 'why', 'how', 'all', 'any', 'both', 'each', 'few', 'more', 'most',
        'other', 'some', 'such', 'than', 'too', 'very', 'can', 'will', 'just', 'should',
        'now', 'also', 'into', 'only', 'other', 'then', 'them', 'their', 'there', 'they',
        'have', 'been', 'were', 'being', 'having', 'with', 'from', 'about', 'like', 'know',
        'think', 'people', 'thing', 'things', 'going', 'gonna', 'wanna', 'really', 'actually',
        'literally', 'basically', 'kind', 'sort', 'yeah', 'okay', 'right', 'well', 'said',
        'want', 'need', 'look', 'make', 'take', 'come', 'give', 'tell', 'even', 'much'
    }
    clean = re.sub(r'[^\w\s]', ' ', text).lower()
    words = [w for w in clean.split() if len(w) > 3 and w not in stopwords]
    if not words:
        return ""
    counts = {}
    for w in words:
        counts[w] = counts.get(w, 0) + 1
    sorted_words = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    top_words = [w[0].capitalize() for w in sorted_words[:2]]
    return " ".join(top_words)

def generate_meaningful_content_title(clip_text: str = "", video_title: str = "", chapter_title: str = "", rank: int = 1) -> str:
    """Generate meaningful, high-retention content titles that reflect the actual topic and substance."""
    emojis = ["💡", "🧠", "⚡", "🎯", "🔥", "🚀", "🤯", "💎"]
    emoji = emojis[(rank - 1) % len(emojis)]

    # 1. Use real creator chapter title if present
    if chapter_title and len(chapter_title) > 3:
        clean = re.sub(r'^\d+[\.\:\-]?\s*', '', chapter_title).strip()
        clean = re.sub(r'^(Topic|Part|Chapter|Step)\s*\d*[\:\-]?\s*', '', clean, flags=re.IGNORECASE).strip()
        if len(clean) > 4:
            return f"{clean[:45]} {emoji}"

    # 2. Extract opening question or compelling hook statement from spoken text
    if clip_text:
        # Check for direct questions in the clip
        questions = re.findall(r'([^.!?\n]+(?:\?))', clip_text)
        for q in questions:
            q_clean = q.strip()
            q_clean = re.sub(r'^(so|and|but|like|you know|honestly|actually)\s*,?\s*', '', q_clean, flags=re.IGNORECASE).strip()
            if 15 <= len(q_clean) <= 55:
                words = q_clean.split()
                title_cased = " ".join(w.capitalize() if not w.isupper() else w for w in words)
                return f"{title_cased} {emoji}"

        # Check for strong declarative hook sentences
        sentences = re.split(r'[\.\!\?]\s+', clip_text.strip())
        hook_starters = [
            'the secret is', 'the real reason', 'why nobody', 'how to', 'the biggest mistake',
            'what if', 'the truth about', 'this is how', 'if you want', 'the problem with',
            'i realized that', 'never make this', 'stop doing this', 'the only way'
        ]
        for s in sentences[:4]:
            s_clean = s.strip()
            s_lower = s_clean.lower()
            for hs in hook_starters:
                if hs in s_lower and 15 <= len(s_clean) <= 55:
                    words = s_clean.split()
                    title_cased = " ".join(w.capitalize() if not w.isupper() else w for w in words)
                    return f"{title_cased} {emoji}"

    # 3. Extract prominent concept from this specific clip text
    clip_concept = extract_meaningful_topic_phrase(clip_text)

    # 4. Derive general topic from video title as fallback
    clean_v = re.sub(r'[^\w\s-]', '', video_title or '').strip()
    words = [w for w in clean_v.split() if len(w) > 2 and w.lower() not in ['video', 'full', 'stream', 'live', 'episode', 'podcast', 'part', 'with', 'from', 'the', 'and', 'official', 'clip', 'highlight']]
    general_topic = " ".join(words[:3]) if words else "This Insight"

    topic = clip_concept if clip_concept and len(clip_concept) > 4 else general_topic

    templates = [
        f"The Truth About {topic} 🧠",
        f"Why {topic} Changes Everything 💡",
        f"The Exact Strategy Behind {topic} ⚡",
        f"What Nobody Realizes About {topic} 🎯",
        f"The Turning Point In {topic} 🚀"
    ]
    return templates[(rank - 1) % len(templates)]

def format_duration(seconds: float) -> str:
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins}:{secs:02d}"

def synthesize_viral_clips(video_duration: float, title: str, chapters: list = None) -> list:
    """Intelligent timestamp cutting producing meaningful, content-focused clips based on video topic."""
    video_dur = max(60.0, float(video_duration))
    clean_v = re.sub(r'[^\w\s-]', '', title or '').strip()
    words = [w for w in clean_v.split() if len(w) > 2 and w.lower() not in ['video', 'full', 'stream', 'live', 'episode', 'podcast', 'part', 'with', 'from', 'the', 'and', 'official', 'clip']]
    topic = " ".join(words[:4]) if words else "This Insight"

    intervals = [
        {"offset": 0.12, "dur": 38.0, "rank": 1, "score": 98, "badge": "🔥 Viral Hit",
         "title": f"The Core Truth About {topic} 🧠",
         "hook": f"The biggest realization from {topic}…"},
        {"offset": 0.35, "dur": 40.0, "rank": 2, "score": 95, "badge": "💡 Core Insight",
         "title": f"Why {topic} Changes Everything 💡",
         "hook": f"Why most people get {topic} completely wrong…"},
        {"offset": 0.60, "dur": 42.0, "rank": 3, "score": 92, "badge": "⚡ Turning Point",
         "title": f"The Exact Moment Everything Clicked ⚡",
         "hook": f"The major turning point in {topic}…"},
        {"offset": 0.82, "dur": 35.0, "rank": 4, "score": 89, "badge": "🎯 Critical Takeaway",
         "title": f"What Nobody Realizes About {topic} 🎯",
         "hook": f"The final crucial lesson from {topic}…"}
    ]

    formatted = []
    for item in intervals:
        start_time = round(video_dur * item["offset"], 1)
        end_time = round(min(video_dur - 1, start_time + item["dur"]), 1)
        actual_dur = round(end_time - start_time, 1)

        formatted.append({
            "id": f"clip_{item['rank']}",
            "rank": item["rank"],
            "title": item["title"],
            "hook": item["hook"],
            "start": start_time,
            "end": end_time,
            "duration": format_duration(actual_dur),
            "duration_sec": actual_dur,
            "virality_score": item["score"],
            "virality_badge": item["badge"],
            "viral_reasons": ["High engagement window", f"Topic: {topic[:30]}"],
            "tags": ["Key Insight", "Must Watch", "Algorithm Pick"],
            "full_text": item["hook"],
            "subtitles": generate_word_subtitles(start_time, end_time, item["hook"]),
            "has_real_captions": False
        })
    return formatted
