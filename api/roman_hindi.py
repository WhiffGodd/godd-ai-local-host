"""Render Devanagari captions as readable Roman Hindi without changing timings."""

import re
import unicodedata


DEVANAGARI = re.compile(r"[\u0900-\u0963\u0971-\u097F][\u0900-\u0963\u0971-\u097F\u200C\u200D]*")
VOWELS = dict(zip("अआइईउऊऋएऐओऔऍऑ", (
    "a", "aa", "i", "ee", "u", "oo", "ri", "e", "ai", "o", "au", "e", "o",
)))
SIGNS = dict(zip("ािीुूृेैोौॅॉ", (
    "aa", "i", "ee", "u", "oo", "ri", "e", "ai", "o", "au", "e", "o",
)))
CONSONANTS = dict(zip("कखगघङचछजझञटठडढणतथदधनपफबभमयरलवशषसह", (
    "k", "kh", "g", "gh", "ng", "ch", "chh", "j", "jh", "ny", "t", "th",
    "d", "dh", "n", "t", "th", "d", "dh", "n", "p", "ph", "b", "bh",
    "m", "y", "r", "l", "v", "sh", "sh", "s", "h",
)))
NUKTA = {"क": "q", "ख": "kh", "ग": "gh", "ज": "z", "ड": "d", "ढ": "dh", "फ": "f"}
COMMON = {
    "मैं": "main", "में": "mein", "है": "hai", "हैं": "hain", "हूँ": "hoon",
    "हूं": "hoon", "हाँ": "haan", "हां": "haan", "नहीं": "nahi", "नही": "nahi",
    "यह": "yeh", "वह": "woh", "ये": "ye", "वो": "woh", "वोही": "wohi",
    "क्या": "kya", "क्यों": "kyun", "क्योंकि": "kyunki", "कैसे": "kaise",
    "अच्छा": "achha", "अच्छी": "achhi", "अच्छे": "achhe", "बहुत": "bahut",
    "लिए": "liye", "चाहिए": "chahiye", "चाहिये": "chahiye",
    "आपको": "aapko", "आपका": "aapka", "आपकी": "aapki", "आपके": "aapke",
    "मुझे": "mujhe", "तुम्हें": "tumhein", "तुम्हारे": "tumhare",
    "उन्हें": "unhein", "उन्होंने": "unhone", "उनका": "unka", "उसका": "uska",
    "उसके": "uske", "उसकी": "uski", "हमारा": "hamara", "हमारे": "hamare",
    "हमेशा": "hamesha", "अपना": "apna", "अपने": "apne", "अपनी": "apni",
    "करना": "karna", "करते": "karte", "करती": "karti", "करता": "karta",
    "करेंगे": "karenge", "रहना": "rehna", "रहा": "raha", "रही": "rahi",
    "बोलना": "bolna", "बताओ": "batao", "बताइए": "bataiye",
    "नमस्ते": "namaste", "दोस्तों": "doston", "दोस्त": "dost",
    "देखो": "dekho", "देखना": "dekhna", "देखते": "dekhte",
    "खेलना": "khelna", "करके": "karke", "चलो": "chalo",
    "समझना": "samajhna", "समझते": "samajhte", "बदलना": "badalna",
    "सकता": "sakta", "सकती": "sakti", "सकते": "sakte",
    "वीडियो": "video", "गेम": "game", "गेमिंग": "gaming", "स्ट्रीम": "stream",
    "मिनट": "minute", "सेकंड": "second", "नया": "naya", "नई": "nayi",
    "चैनल": "channel", "सब्सक्राइब": "subscribe", "लाइक": "like", "शॉर्ट्स": "shorts",
    "हिंदी": "Hindi", "हिन्दी": "Hindi", "इंग्लिश": "English",
}
PUNCTUATION_AND_DIGITS = str.maketrans("।॥०१२३४५६७८९", "..0123456789")


def _roman_word(match):
    word = unicodedata.normalize("NFC", match[0]).replace("\u200c", "").replace("\u200d", "")
    if word in COMMON:
        return COMMON[word]

    # Each unit records its consonant and vowel. A bare consonant supplies an
    # implicit 'a' unless it ends the word or Hindi pronunciation drops it.
    units = []
    for index, char in enumerate(word):
        if char in CONSONANTS:
            units.append([CONSONANTS[char], "a", True])
        elif char in VOWELS:
            units.append(["", VOWELS[char], False])
        elif units and char == "़":
            units[-1][0] = NUKTA.get(word[index - 1], units[-1][0])
        elif units and (char in SIGNS or char == "्"):
            units[-1][1:] = [SIGNS.get(char, ""), False]
        elif char in "ंँः":
            units.append(["", "h" if char == "ः" else "n", False])
        else:
            units.append(["", char, False])

    if len(units) > 1 and units[-1][2]:
        units[-1][1] = ""
    # A medial schwa between sounded syllables is often silent, as in
    # लिखना (likhna). Work right to left so deletions do not stack.
    for i in range(len(units) - 2, 0, -1):
        if units[i][2] and units[i - 1][1] and units[i + 1][0] and units[i + 1][1]:
            units[i][1] = ""
    return "".join(onset + vowel for onset, vowel, _ in units)


def roman_hindi(text):
    if not text:
        return text
    return DEVANAGARI.sub(_roman_word, text).translate(PUNCTUATION_AND_DIGITS)


def romanize_cues(cues, field):
    """Copy timed cues with converted text, preserving all other fields."""
    return [{**cue, field: roman_hindi(cue.get(field, ""))} for cue in cues or ()]


def romanize_clip_captions(clip):
    clip["full_text"] = roman_hindi(clip.get("full_text", ""))
    if "subtitles" in clip:
        clip["subtitles"] = romanize_cues(clip["subtitles"], "word")
    if "video_subtitles" in clip:
        clip["video_subtitles"] = romanize_cues(clip["video_subtitles"], "text")


def romanize_speech(segments):
    return [{**segment, "text": roman_hindi(segment.get("text", "")),
             "words": romanize_cues(segment.get("words"), "word")} for segment in segments]
