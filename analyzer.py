from api.youtube_access import youtube_options, extract_youtube_info
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
            info = extract_youtube_info(url, ydl_opts)
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
        }
        info = extract_youtube_info(url, ydl_opts)
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
                if not segs:
                    continue

                # Extract words with millisecond precision from json3 tOffsetMs
                words_in_ev = []
                text_parts = []
                for s in segs:
                    raw_w = s.get('utf8', '').replace("\n", " ").strip()
                    cleaned_w = clean_streamer_text(raw_w)
                    if not cleaned_w:
                        continue
                    text_parts.append(cleaned_w)
                    t_offset = s.get('tOffsetMs')
                    w_start = round(start_sec + (t_offset / 1000.0), 2) if t_offset is not None else None
                    words_in_ev.append({
                        "word": cleaned_w,
                        "start": w_start
                    })

                cleaned = " ".join(text_parts).strip()
                if cleaned and len(cleaned) > 1:
                    # Link end times of words
                    for idx, wm in enumerate(words_in_ev):
                        if wm["start"] is not None:
                            next_start = words_in_ev[idx + 1]["start"] if idx + 1 < len(words_in_ev) else None
                            if next_start is not None and next_start > wm["start"]:
                                wm["end"] = next_start
                            else:
                                wm["end"] = round(wm["start"] + 0.35, 2)

                    results.append({
                        "text": cleaned,
                        "start": round(start_sec, 2),
                        "duration": round(dur_sec, 2),
                        "end": round(start_sec + dur_sec, 2),
                        "words": words_in_ev if any(w["start"] is not None for w in words_in_ev) else []
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

    # Method 1: Try yt-dlp timedtext first (json3 contains true millisecond word-level timing)
    if url:
        print(f"[Transcript] Trying high-precision yt-dlp timedtext for {video_id} (is_english={is_english})...")
        ytdlp_segments = fetch_transcript_from_ytdlp(video_id, url, is_english=is_english)
        if ytdlp_segments and len(ytdlp_segments) >= 5:
            print(f"[Transcript] yt-dlp extracted {len(ytdlp_segments)} segments with high-precision word timing.")
            return ytdlp_segments

    # Method 2: YouTubeTranscriptApi fallback
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

    print(f"[Transcript] Total real spoken segments extracted: {len(results)}")
    return results

def estimate_word_weight(word: str) -> float:
    """
    Estimate relative spoken time for a word based on syllables, character length and punctuation.
    Allows subtitles to dynamically adapt when the speaker speaks fast vs slow.
    """
    w = re.sub(r'[^\w]', '', str(word or '')).strip()
    if not w:
        return 0.8
    vowels = len(re.findall(r'[aeiouy]+', w.lower()))
    syllables = max(1, vowels)
    weight = 0.35 + (syllables * 0.42) + (len(w) * 0.04)
    raw = str(word or '').strip()
    if raw.endswith((".", "!", "?")):
        weight += 0.80  # Full sentence terminal pause
    elif raw.endswith((",", ";", ":", "-")):
        weight += 0.40  # Clause breathing pause
    return max(0.5, weight)

from api.clip_boundaries import select_short_clip_windows, snap_to_clean_sentence_boundaries

def generate_word_subtitles_from_segments(segments: list, clip_start: float, clip_end: float) -> list:
    """
    Extract word-level subtitle timings from real spoken transcript segments.
    Applies adaptive speech rate weighting so fast and slow speech are accurately tracked.
    """
    if not segments:
        return []
    clip_segs = [s for s in segments if s.get("end", 0) >= clip_start and s.get("start", 0) <= clip_end]
    if not clip_segs:
        return []

    subtitles = []

    for seg in clip_segs:
        segment_start = float(seg.get("start", 0))
        segment_end = float(seg.get("end", segment_start + 1.0))
        s_start = max(clip_start, segment_start)
        s_end = min(clip_end, segment_end)
        if s_end <= s_start:
            continue

        words_meta = seg.get("words") or []
        if any(wm.get("start") is not None for wm in words_meta):
            # Fill only missing offsets between the surrounding word starts.
            # Keep the original metadata intact for other overlapping clips.
            starts = [float(wm["start"]) if wm.get("start") is not None else None
                      for wm in words_meta]
            anchors = [(-1, segment_start)]
            anchors.extend((i, time) for i, time in enumerate(starts) if time is not None)
            anchors.append((len(starts), segment_end))
            for (left, before), (right, after) in zip(anchors, anchors[1:]):
                first_missing = left + 1
                if first_missing == right:
                    continue
                # Leading words can begin at the start of their caption cue.
                slots = right - left if left >= 0 else right
                for index in range(first_missing, right):
                    step = index - left if left >= 0 else index
                    starts[index] = before + max(0.0, after - before) * step / slots

            for i, wm in enumerate(words_meta):
                w_clean = re.sub(r'[«»<>]+', '', wm.get("word", "")).strip()
                if not w_clean:
                    continue
                next_start = starts[i + 1] if i + 1 < len(starts) else segment_end
                raw_end = float(wm["end"]) if wm.get("end") is not None else next_start
                if i + 1 < len(starts) and words_meta[i + 1].get("start") is None:
                    raw_end = min(raw_end, next_start)
                w_start = max(clip_start, round(starts[i], 3))
                w_end = min(clip_end, round(raw_end, 3))
                if w_end <= w_start:
                    continue
                subtitles.append({
                    "word": w_clean,
                    "start": w_start,
                    "end": w_end,
                    "highlight": any(k in w_clean.lower() for k in ["important", "key", "secret", "never", "why", "how", "truth", "future", "mind", "huge", "biggest", "realize", "best", "worst"])
                })
            continue

        # Clean text
        cleaned_text = re.sub(r'&(?:lt|gt|amp|quot|apos);?', ' ', str(seg.get("text", "")))
        cleaned_text = re.sub(r'[«»<>]+', ' ', cleaned_text)
        raw_words = [w.strip() for w in cleaned_text.split() if w.strip()]
        if not raw_words:
            continue

        seg_dur = max(0.25, s_end - s_start)
        weights = [estimate_word_weight(w) for w in raw_words]
        total_weight = sum(weights) or 1.0

        cur = s_start
        for idx, w in enumerate(raw_words):
            w_clean = re.sub(r'[«»<>]+', '', w).strip()
            if not w_clean:
                continue
            word_fraction = weights[idx] / total_weight
            duration = seg_dur * word_fraction
            w_end = min(s_end, round(cur + duration, 3))
            subtitles.append({
                "word": w_clean,
                "start": round(cur, 2),
                "end": w_end,
                "highlight": any(k in w_clean.lower() for k in ["important", "key", "secret", "never", "why", "how", "truth", "future", "mind", "huge", "biggest", "realize", "best", "worst"])
            })
            cur = cur + duration
    return subtitles

def generate_word_subtitles(start_sec: float, end_sec: float, text: str) -> list:
    """Generate fine-grained word timings for animated karaoke subtitles with lead time."""
    clean_text = re.sub(r'[«»<>]+', ' ', text or '')
    words = [w.strip() for w in clean_text.split() if w.strip()]
    if not words:
        return []

    lead_offset = 0.0
    adj_start = max(0.0, start_sec - lead_offset)
    total_duration = max(0.5, end_sec - adj_start)
    weights = [estimate_word_weight(w) for w in words]
    total_weight = sum(weights) or 1.0

    subtitles = []
    current_time = adj_start
    for i, word in enumerate(words):
        w_clean = re.sub(r'[«»<>]+', '', word).strip()
        if not w_clean:
            continue
        duration = max(0.18, total_duration * (weights[i] / total_weight))
        w_end = min(end_sec, current_time + duration)
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
    if not transcript:
        return []

    chapter_ranges = []
    if chapters and len(chapters) >= 2:
        ignore_words = ["intro", "outro", "sponsor", "welcome", "subscribe", "disclaimer", "patreon", "merch", "credits"]
        filtered_chapters = [
            ch for ch in chapters 
            if not any(w in str(ch.get("title", "")).lower() for w in ignore_words)
        ]
        if not filtered_chapters:
            filtered_chapters = chapters
        all_starts = sorted({float(ch.get("time", ch.get("start_time", 0))) for ch in chapters})
        ends = dict(zip(all_starts, all_starts[1:] + [video_duration]))
        chapter_ranges = sorted(
            (start, min(ends[start], video_duration), str(ch.get("title", "")))
            for ch in filtered_chapters
            for start in [float(ch.get("time", ch.get("start_time", 0)))]
            if start < video_duration
        )

    short_windows = select_short_clip_windows(
        transcript, video_duration, [(start, end) for start, end, _ in chapter_ranges])
    if chapter_ranges and not short_windows:
        meaningful_clips = []
        for start_time, chapter_end, ch_title in chapter_ranges:
            idx = len(meaningful_clips)
            
            c_start, c_end, c_segs = snap_to_clean_sentence_boundaries(
                transcript,
                start_time,
                min_duration=35.0,
                ideal_duration=58.0,
                max_duration=85.0,
                boundary_limit=chapter_end
            )
            if not c_segs:
                continue
            actual_dur = round(c_end - c_start, 1)
            full_text = " ".join(s.get("text", "") for s in c_segs) if c_segs else ch_title
            
            clip_title = generate_meaningful_content_title(clip_text=full_text, video_title=title, chapter_title=ch_title, rank=idx+1)
            
            c_vsubs = [
                {
                    "start": round(float(s.get("start", 0)), 2),
                    "end": round(float(s.get("end", 0)), 2),
                    "text": clean_streamer_text(s.get("text", ""))
                }
                for s in c_segs
                if clean_streamer_text(s.get("text", ""))
            ]

            meaningful_clips.append({
                "id": f"clip_{idx+1}",
                "rank": idx + 1,
                "title": clip_title,
                "hook": ch_title,
                "start": c_start,
                "end": c_end,
                "duration": format_duration(actual_dur),
                "duration_sec": actual_dur,
                "virality_score": 98 - idx * 2,
                "virality_badge": "🔥 Core Highlight" if idx == 0 else "⚡ Key Insight",
                "viral_reasons": ["Creator Chapter Topic", f"Content: {ch_title[:32]}"],
                "tags": ["Key Chapter", "Deep Dive", "Must Watch"],
                "full_text": full_text,
                "video_subtitles": c_vsubs,
                "has_source_subtitles": bool(c_vsubs),
                "subtitles": generate_word_subtitles_from_segments(c_segs, c_start, c_end) or generate_word_subtitles(c_start, c_end, full_text),
                "has_real_captions": bool(c_segs)
            })
            if len(meaningful_clips) == 5:
                break
            
        if meaningful_clips:
            return meaningful_clips

    min_clip_length = 35.0
    candidate_windows = []
    # Search longer exchanges only when no standalone 60–90 second clips fit.
    windows = short_windows or (
        snap_to_clean_sentence_boundaries(transcript, float(seg["start"]), boundary_limit=video_duration)
        for seg in transcript[::max(1, len(transcript) // 30)]
        if float(seg["start"]) + min_clip_length <= video_duration
    )
    seen_starts = set()
    for c_start, c_end, c_segs in windows:
        dur = round(c_end - c_start, 1)
        if not c_segs or dur < min_clip_length or dur > 180.0:
            continue
            
        # Avoid duplicate snapped starts
        start_key = round(c_start, 0)
        if start_key in seen_starts:
            continue
        seen_starts.add(start_key)
        
        words = [s.get("text", "") for s in c_segs]
        full_text = " ".join(words).strip()
        if not full_text:
            continue
            
        score, reasons, tags, hook_text = score_segment(
            start_time=c_start,
            duration=dur,
            text=full_text,
            first_phrase=" ".join(words[:min(5, len(words))])
        )
        
        c_vsubs = [
            {
                "start": round(float(s.get("start", 0)), 2),
                "end": round(float(s.get("end", 0)), 2),
                "text": clean_streamer_text(s.get("text", ""))
            }
            for s in c_segs
            if clean_streamer_text(s.get("text", ""))
        ]
        
        candidate_windows.append({
            "start": round(c_start, 2),
            "end": round(c_end, 2),
            "duration_sec": dur,
            "text": full_text,
            "score": score,
            "reasons": reasons,
            "tags": tags,
            "hook": hook_text,
            "segs": c_segs,
            "video_subtitles": c_vsubs
        })
                    
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
        # Do not replace rejected real speech with arbitrary fixed windows.
        return []
        
    # Format selected clips for Klap-style display
    formatted = []
    for idx, clip in enumerate(selected_clips):
        chapter_title = next((name for start, end, name in chapter_ranges
                              if start <= clip["start"] and clip["end"] <= end), "")
        viral_title = generate_meaningful_content_title(
            clip_text=clip["text"], video_title=title, chapter_title=chapter_title, rank=idx + 1)
        
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
            "video_subtitles": clip.get("video_subtitles", []),
            "has_source_subtitles": bool(clip.get("video_subtitles")),
            "subtitles": generate_word_subtitles_from_segments(clip["segs"], clip["start"], clip["end"]) or generate_word_subtitles(clip["start"], clip["end"], clip["text"]),
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

    # 8. Preferred Short Duration
    if 60 <= duration <= 90:
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
