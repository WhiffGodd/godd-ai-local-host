"""Transcript boundary selection shared by local and hosted analysis."""

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


def snap_to_clean_sentence_boundaries(transcript, target_start, min_duration=35.0,
                                      ideal_duration=58.0, max_duration=85.0,
                                      completion_limit=180.0, boundary_limit=None):
    """Prefer thought endings; max_duration is soft, completion_limit is hard.

    A hard limit never licenses cutting an unfinished transcript segment. Return
    no segments when no defensible ending exists. This is a heuristic, not a
    semantic guarantee that a speaker has answered every part of a question.
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
    hard_end = start + max(max_duration, completion_limit)
    if boundary_limit is not None:
        hard_end = min(hard_end, boundary_limit)
    candidates = []
    for i in range(start_idx, len(transcript)):
        seg = transcript[i]
        end = float(seg.get("end", float(seg.get("start", 0)) + float(seg.get("duration", 0))))
        if end > hard_end:
            break
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
        at_end = next_seg is None or (boundary_limit is not None and float(next_seg.get("start", 0)) >= boundary_limit)
        conclusion = terminal and any(phrase in text.lower() for phrase in CONCLUSIONS)
        strong = topic_change or at_end or conclusion or gap >= 1.2 or (terminal and gap >= 0.65)
        if not (terminal or strong):
            continue
        # A paragraph/pause/conclusion outweighs the short-form duration target.
        # Sentence-only fallbacks stay inside the soft limit.
        if not strong and end - start > max_duration:
            continue
        score = (100 if strong else 0) + (30 if topic_change else 0) + (20 if conclusion else 0)
        score -= abs((end - start) - ideal_duration) * 0.15
        candidates.append((score, i, end, gap))
    if not candidates:
        return start, start, []
    _, end_idx, end, gap = max(candidates, key=lambda c: c[0])
    # Add room for vocal decay only where it does not enter the next utterance.
    padding = min(0.3, gap / 2) if end_idx + 1 < len(transcript) else 0.0
    end = min(hard_end, end + padding)
    return round(start, 2), round(end, 2), transcript[start_idx:end_idx + 1]
