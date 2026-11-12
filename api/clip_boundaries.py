"""Transcript boundary selection shared by local and hosted analysis."""

import re
from bisect import bisect_left, bisect_right
from dataclasses import dataclass

INCOMPLETE_TAIL_WORDS = {
    "and", "but", "so", "or", "because", "if", "while", "though", "although", "whereas",
    "as", "since", "plus", "yet", "that", "which", "who", "whom", "whose", "where", "when",
    "what", "whatever", "how", "why", "the", "a", "an", "this", "these", "those",
    "my", "your", "his", "her", "its", "our", "their", "of", "to", "in", "for", "on",
    "with", "at", "by", "from", "up", "about", "into", "through", "over", "after",
    "under", "between", "against", "during", "without", "before", "towards", "upon",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do",
    "does", "did", "can", "could", "will", "would", "shall", "should", "may", "might",
    "must", "like", "representing", "distinct", "including", "than", "well", "just"
}


# These introduce another part of the same explanation, rather than a new topic.
CONTINUATIONS = ("and ", "but ", "because ", "so ", "also ", "for example", "for instance",
                 "in other words", "that means", "which means", "the reason", "first,",
                 "second,", "third,", "another reason", "aur ", "lekin ", "kyunki ")
TOPIC_CHANGES = ("moving on", "next question", "another question", "let's move",
                 "lets move", "on a different", "our next topic")
CONCLUSIONS = ("that's why", "that is why", "that's how", "that is how", "in conclusion",
               "to sum up", "the takeaway", "that's it", "it's that simple", "in the end")
DIRECT_QUESTION = re.compile(
    r"^(?:(?:okay|so|and|but|well)[,.]?\s+)*"
    r"(?:tell me\b|(?:how|why|what|when|where|who|which)\s+"
    r"(?:do|does|did|is|are|was|were|can|could|would|should|will|has|have|to)\b"
    r"|(?:can|could|would|do|did|have)\s+you\b|is there\b)",
    re.IGNORECASE,
)
SENTENCE_END = re.compile(r"""([.!?।]+)[\"'”’)]*$""")
RHETORICAL_QUESTION = ("do you understand", "do you know what i mean", "what do i mean")
ANSWER_CONTINUATIONS = (*CONTINUATIONS, "i mean", "cuz ", "you know,")
SHORT_MIN, SHORT_TARGET, SHORT_MAX = 60.0, 75.0, 90.0
MAX_CLIP_SECONDS = 120.0
SPEECH_RESTART = re.compile(r"^(?:okay|ok|oh|yo|now|wait|all right|alright|nice|look|here|watch)\b", re.I)
DEPENDENT_START = re.compile(
    r"^(?:and|but|so|because|then|also|which|that|this|these|those|it|they|he|she"
    r"|yes|no|right|yeah|exactly|like|um|uh|okay|well|to|by|cuz|you know|i mean)\b",
    re.IGNORECASE,
)
TAG_QUESTION = re.compile(r",\s*(?:right|okay|you know)\?$", re.IGNORECASE)


@dataclass(frozen=True)
class Sentence:
    text: str
    cue: int
    word: int
    start: float | None
    last_cue: int
    end: float
    punctuation: str


def timed_sentences(transcript, start_idx, hard_end):
    """Recover sentence boundaries and keep exact offsets where captions have them."""
    sentence = []
    for index in range(start_idx, len(transcript)):
        segment = transcript[index]
        if float(segment["start"]) > hard_end + 12:
            break
        words = segment.get("words") or [
            {"word": word} for word in str(segment.get("text", "")).split()
        ]
        for word_idx, word in enumerate(words):
            token = word["word"]
            offset = word.get("start")
            if offset is None and word_idx == 0:
                offset = float(segment["start"])
            if not sentence:
                sentence_start = (index, word_idx, offset)
            sentence.append(token)
            punctuation = SENTENCE_END.search(token)
            if punctuation:
                if word.get("end") is not None:
                    end = float(word["end"])
                else:
                    end = float(segment["end"])
                    if index + 1 < len(transcript):
                        end = min(end, float(transcript[index + 1]["start"]))
                yield Sentence(" ".join(sentence), *sentence_start, index, end, punctuation[1])
                sentence.clear()


def direct_questions(transcript, start_idx, hard_end):
    """Yield question starts, even when rolling captions split the question."""
    for sentence in timed_sentences(transcript, start_idx, hard_end):
        if "?" in sentence.punctuation and DIRECT_QUESTION.match(sentence.text):
            yield (sentence.cue, sentence.word, sentence.start), sentence.last_cue, sentence.text.lower()


def short_clip_windows(transcript, video_duration, ranges=()):
    """Find self-contained 60–90 second excerpts across the source."""
    sentences = list(timed_sentences(transcript, 0, video_duration))
    openings = []
    for sentence in sentences:
        text = sentence.text.lower()
        if sentence.start is None or len(text.split()) < 5:
            continue
        if "?" in sentence.punctuation:
            if not DIRECT_QUESTION.match(text) or text.endswith(("that?", "it?")):
                continue
        elif DEPENDENT_START.match(text) or text.startswith((*CONTINUATIONS, *CONCLUSIONS, *TOPIC_CHANGES)):
            continue
        openings.append(sentence)
    openings.sort(key=lambda sentence: sentence.start)
    start_times = [sentence.start for sentence in openings]
    chapter_ends = [upper for _, upper in ranges]
    for index, closing in enumerate(sentences):
        if "?" in closing.punctuation and not TAG_QUESTION.search(closing.text):
            continue
        if closing.text.split()[-1].lower().strip(".,!?:;\"'()[]।") in INCOMPLETE_TAIL_WORDS:
            continue
        following = sentences[index + 1] if index + 1 < len(sentences) else None
        follow_text = following.text.lower() if following else ""
        follow_up = bool(following and "?" in following.punctuation
                         and DIRECT_QUESTION.match(follow_text) and len(follow_text.split()) >= 6
                         and not follow_text.startswith(RHETORICAL_QUESTION)
                         and not closing.text.lower().startswith("and the other ")
                         and following.last_cue + 1 < len(transcript)
                         and not transcript[following.last_cue + 1]["text"].lower().startswith(ANSWER_CONTINUATIONS))
        next_topic = follow_text.startswith(TOPIC_CHANGES)
        final_sentence = closing.last_cue == len(transcript) - 1 and following is None
        chapter_boundary = any(0 <= upper - closing.end <= 2 for upper in chapter_ends)
        summary = closing.text.lower().startswith(CONCLUSIONS) and not follow_text.startswith(ANSWER_CONTINUATIONS)
        if not (follow_up or next_topic or final_sentence or chapter_boundary or summary):
            continue
        end = min(closing.end, video_duration)
        if following and following.start is not None:
            end = min(end + 0.12, following.start, video_duration)
        end = round(end, 2)
        first = bisect_left(start_times, round(end - SHORT_MAX, 2))
        last = bisect_right(start_times, round(end - SHORT_MIN, 2))
        for opening in openings[first:last]:
            if ranges and not any(lower <= opening.start and end <= upper for lower, upper in ranges):
                continue
            # A summary can close an excerpt from an explanation. For clips
            # starting with a question, require the complete exchange.
            if ("?" in opening.punctuation
                    and not (follow_up or next_topic or final_sentence or chapter_boundary)):
                continue
            start = round(opening.start, 2)
            if not SHORT_MIN <= round(end - start, 2) <= SHORT_MAX:
                continue
            end_cue = closing.last_cue + 1
            end_word = 0
            if following and following.cue == closing.last_cue:
                if following.start is None:
                    continue
                end_cue, end_word = following.cue, following.word
            segments = clip_before_question(transcript, opening.cue, end_cue, end_word, end)
            if not segments:
                continue
            if opening.word:
                cue = segments[0]
                words = cue["words"][opening.word:]
                segments[0] = {**cue, "start": start, "duration": cue["end"] - start,
                               "words": words, "text": " ".join(word["word"] for word in words)}
            quality = 2 if follow_up or next_topic or chapter_boundary else 1
            if opening.text.lower().startswith(("you ", "i ", "we ")):
                quality -= 0.25
            yield start, end, segments, quality


def select_short_clip_windows(transcript, video_duration, ranges=(), limit=5):
    ranked = sorted(short_clip_windows(transcript, video_duration, ranges),
                    key=lambda clip: (-clip[3], abs(clip[1] - clip[0] - SHORT_TARGET)))
    if not ranked and not any(re.search(r"[.!?।](?:\s|$)", cue["text"]) for cue in transcript):
        ranked = sorted(pause_clip_windows(transcript, video_duration, ranges),
                        key=lambda clip: (-clip[3], abs(clip[1] - clip[0] - SHORT_TARGET)))
    selected = []

    def add(candidates):
        for clip in candidates:
            start, end, _, _ = clip
            if all(end <= other[0] or start >= other[1] for other in selected):
                selected.append(clip)
                return

    for lower, upper in ranges:
        add(clip for clip in ranked if lower <= clip[0] and clip[1] <= upper)
        if len(selected) == limit:
            break
    while len(selected) < limit:
        count = len(selected)
        add(ranked)
        if len(selected) == count:
            break
    if ranges:
        selected.sort(key=lambda clip: clip[0])
    return [(start, end, segments) for start, end, segments, _ in selected]


def pause_clip_windows(transcript, video_duration, ranges):
    """Find passages between measured pauses and fresh utterances in plain captions."""
    cuts = []
    for index, (cue, following) in enumerate(zip(transcript, transcript[1:])):
        words = cue.get("words") or []
        if not words or words[-1].get("end") is None:
            continue
        last_word = words[-1]["word"].lower().strip(".,!?:;\"'()[]")
        if not last_word or last_word in INCOMPLETE_TAIL_WORDS:
            continue
        start_next = float(following["start"])
        end = min(float(cue["end"]), float(words[-1]["end"]))
        gap = start_next - end
        if gap < 1.15 or not SPEECH_RESTART.match(following["text"].strip()):
            continue
        cuts.append((index + 1, round(end + min(0.18, gap / 2), 2), round(start_next, 2), min(gap, 3)))

    for section_start, section_end in ranges or [(0, video_duration)]:
        opening_cuts = [cut for cut in cuts if section_start <= cut[2] < section_end]
        for opening_index, (first, _, start, opening_gap) in enumerate(opening_cuts):
            for closing_index in range(opening_index + 1, len(opening_cuts)):
                stop, end, _, closing_gap = opening_cuts[closing_index]
                duration = round(end - start, 2)
                if duration > SHORT_MAX or end > section_end:
                    break
                if duration < SHORT_MIN:
                    continue
                segments = clip_before_question(transcript, first, stop, 0, end)
                yield start, end, segments, opening_gap + closing_gap


def clip_before_question(transcript, start_idx, question_idx, word_idx, end):
    """Keep the speech before a handoff without displaying the next question."""
    segments = transcript[start_idx:question_idx]
    if word_idx:
        segment = transcript[question_idx]
        words = segment["words"][:word_idx]
        segments.append({
            **segment,
            "text": " ".join(word["word"] for word in words),
            "words": words,
            "end": end,
            "duration": end - float(segment["start"]),
        })
    # Rolling caption display times can extend into the following speaker's turn.
    for i, segment in enumerate(segments):
        if float(segment["end"]) > end:
            segments[i] = {**segment, "end": end, "duration": end - float(segment["start"])}
    return segments


def snap_to_clean_sentence_boundaries(transcript, target_start, min_duration=35.0,
                                      ideal_duration=58.0, max_duration=85.0,
                                      completion_limit=MAX_CLIP_SECONDS, boundary_limit=None):
    """Find an exchange or a passage with an identifiable ending.

    Question-led clips need a follow-up, an explicit transition, or the end
    of the transcript. A finished sentence alone can still be mid-answer.
    """
    if not transcript:
        return target_start, target_start, []
    start_idx = min(range(len(transcript)),
                    key=lambda i: abs(float(transcript[i].get("start", 0)) - target_start))
    while start_idx > 0:
        prev = transcript[start_idx - 1]
        gap = float(transcript[start_idx].get("start", 0)) - float(prev.get("end", 0))
        if gap >= 0.8 or str(prev.get("text", "")).rstrip().endswith((".", "!", "?", "।")):
            break
        if target_start - float(prev.get("start", 0)) > 8:
            # This candidate would start inside a long, unfinished sentence.
            return target_start, target_start, []
        start_idx -= 1
    start = float(transcript[start_idx].get("start", target_start))
    hard_end = start + min(completion_limit, MAX_CLIP_SECONDS)
    if boundary_limit is not None:
        hard_end = min(hard_end, boundary_limit)
    # Use an actual follow-up as the end of an exchange. A pause inside an
    # answer is common and must not beat a question that comes after it.
    answer_start = None
    handoff = None
    for (index, word_idx, time), question_end_idx, question in direct_questions(transcript, start_idx, hard_end):
        if time is None or time > hard_end:
            continue
        if question.startswith(RHETORICAL_QUESTION):
            continue
        if answer_start is None:
            if time - start >= min_duration:
                break
            answer_start = float(transcript[question_end_idx]["start"])
            continue
        if time - answer_start < 12:
            answer_start = float(transcript[question_end_idx]["start"])
            continue
        if question_end_idx + 1 < len(transcript):
            reply = str(transcript[question_end_idx + 1].get("text", "")).strip().lower()
            if reply.startswith(ANSWER_CONTINUATIONS):
                continue
        if len(question.split()) >= 6:
            handoff = index, word_idx, time
            break

    candidates = []
    for i in range(start_idx, len(transcript)):
        seg = transcript[i]
        end = float(seg.get("end", float(seg.get("start", 0)) + float(seg.get("duration", 0))))
        if float(seg["start"]) >= (handoff[2] if handoff else hard_end):
            break
        if end > hard_end or (handoff and end >= handoff[2]):
            continue
        if end - start < min_duration:
            continue
        text = str(seg.get("text", "")).strip()
        words = text.split()
        if not words:
            continue
        tail = words[-1].lower().strip(".,!?:;\"'()[]।")
        incomplete = tail in INCOMPLETE_TAIL_WORDS or text.endswith((",", ";", ":", "-", "...", "…", "?"))
        if incomplete:
            continue
        next_seg = transcript[i + 1] if i + 1 < len(transcript) else None
        next_text = str(next_seg.get("text", "")).strip().lower() if next_seg else ""
        gap = max(0, float(next_seg.get("start", end)) - end) if next_seg else 0
        terminal = text.endswith((".", "!", "।"))
        topic_change = next_text.startswith(TOPIC_CHANGES)
        continuation = next_text.startswith(CONTINUATIONS)
        # Capitalization is unreliable in automatic captions; use actual pauses
        # and connective phrases instead of rejecting every lowercase segment.
        if continuation and gap < 1.5:
            continue
        at_end = next_seg is None and terminal
        if topic_change or at_end:
            padding = min(0.3, gap / 2)
            return round(start, 2), round(min(hard_end, end + padding), 2), transcript[start_idx:i + 1]
        if (answer_start is None and terminal and text.lower().startswith(CONCLUSIONS)
                and end - start <= max_duration):
            candidates.append((abs((end - start) - ideal_duration), i, end, gap))
    if handoff:
        index, word_idx, end = handoff
        segments = clip_before_question(transcript, start_idx, index, word_idx, end)
        if segments and end - start >= min_duration:
            return round(start, 2), round(end, 2), segments
        return start, start, []
    if not candidates:
        return start, start, []
    _, end_idx, end, gap = min(candidates, key=lambda c: c[0])
    # Add room for vocal decay only where it does not enter the next utterance.
    padding = min(0.3, gap / 2) if end_idx + 1 < len(transcript) else 0.0
    end = min(hard_end, end + padding)
    return round(start, 2), round(end, 2), transcript[start_idx:end_idx + 1]
