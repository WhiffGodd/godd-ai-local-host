"""Source-grounded descriptions and topic hashtags for exported clips."""

import re


TOPIC_TAGS = (
    (r"\b(?:minecraft|fortnite|roblox|counter-strike|warzone|gta)\b", None),
    (r"\b(?:gameplay|gaming|clutch|esports|streamer|ranked)\b", "Gaming"),
    (r"\b(?:podcast|interview)\b", "PodcastClips"),
    (r"\b(?:psychology|psychological)\b", "Psychology"),
    (r"\b(?:fitness|workout|strength training)\b", "Fitness"),
    (r"\b(?:programming|coding|developer|python|javascript)\b", "Coding"),
    (r"\b(?:business|startup|entrepreneur|founder)\b", "Business"),
    (r"\b(?:recipe|cooking|baking)\b", "Cooking"),
    (r"\b(?:tutorial|walkthrough|how to)\b", "HowTo"),
)
VALORANT_TERMS = r"\b(?:valorant|brimstone|killjoy|reyna|vandal|spike planted|ascendant lobby)\b"


def add_clip_metadata(clips, video_title, author="", source_url=""):
    for clip in clips:
        title = re.sub(r"\s+", " ", clip["title"]).strip()
        title = re.sub(r"[^\w?!.)'’-]+$", "", title).strip()
        source_title = re.sub(r"\s+", " ", video_title or "").strip()
        author_name = re.sub(r"\s+", " ", author or "").strip()
        transcript = re.sub(r"\s+", " ", clip.get("full_text") or "").strip()
        context = f"{title} {source_title}"
        valorant = (re.search(VALORANT_TERMS, f"{context} {transcript[:1500]}", re.I)
                    or re.search(r"\bsilver\b.{0,100}\bascendant\b", source_title, re.I))
        hashtags = ["#Valorant", "#Gaming"] if valorant else []
        for pattern, tag in TOPIC_TAGS:
            match = re.search(pattern, context, re.I)
            if match:
                hashtag = "#" + (tag or match[0].title().replace("-", ""))
                if hashtag not in hashtags:
                    hashtags.append(hashtag)
            if len(hashtags) == 3:
                break
        hashtags.append("#Shorts")

        # Only quote a complete, reasonably short line from the real captions.
        quote = next((line.strip() for line in re.split(r"(?<=[.!?।])\s+", transcript)[:4]
                      if 45 <= len(line.strip()) <= 180 and line.endswith((".", "!", "?", "।"))
                      and len(line.split()) >= 8), "")
        source = f"From {source_title[:180]}" if source_title else "From the original video"
        if author_name and author_name.lower() not in ("creator", "streamer"):
            source += f" by {author_name[:80]}"
        description = "\n\n".join(part for part in (
            title or "A highlight from the original video",
            f"“{quote}”" if quote and quote.rstrip(".!?").casefold() != title.rstrip(".!?").casefold() else "",
            f"{source}.\n{source_url}" if source_url else f"{source}.",
            " ".join(hashtags),
        ) if part)
        clip["description"] = description.replace("<", "").replace(">", "")
        clip["hashtags"] = hashtags
        clip["thumbnail_time"] = round(clip["start"] + min(12, (clip["end"] - clip["start"]) * .25), 2)
    return clips
