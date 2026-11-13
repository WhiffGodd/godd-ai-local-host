import unittest

from api.clip_metadata import add_clip_metadata
from api.roman_hindi import roman_hindi
from api.youtube_access import original_caption_formats
from video_engine import generate_srt


class RomanHindiTests(unittest.TestCase):
    def test_mixed_hindi_and_english_keeps_the_spoken_words(self):
        text = "मैं YouTube पर वीडियो देख रहा हूँ। १२ मिनट"
        self.assertEqual(roman_hindi(text), "main YouTube par video dekh raha hoon. 12 minute")
        self.assertEqual(roman_hindi("English 👨‍💻 and déjà vu"), "English 👨‍💻 and déjà vu")
        self.assertEqual(roman_hindi("यह फ़िल्म ज़रूर देखना।"), "yeh film zaroor dekhna.")

    def test_preview_words_and_source_lines_keep_their_timestamps(self):
        clip = {
            "title": "Hindi clip", "start": 10, "end": 12, "full_text": "मैं यहाँ हूँ।",
            "subtitles": [{"word": "मैं", "start": 10.1, "end": 10.3, "highlight": True}],
            "video_subtitles": [{"text": "मैं यहाँ हूँ।", "start": 10.1, "end": 11.2}],
        }
        add_clip_metadata([clip], "Original video")
        self.assertEqual(clip["subtitles"], [{"word": "main", "start": 10.1, "end": 10.3, "highlight": True}])
        self.assertEqual(clip["full_text"], "main yahaan hoon.")
        self.assertEqual(clip["video_subtitles"], [{"text": "main yahaan hoon.", "start": 10.1, "end": 11.2}])

    def test_srt_converts_source_captions_with_unchanged_cue_times(self):
        self.assertEqual(
            generate_srt([], 10, [{"text": "आप कैसे हैं?", "start": 10.5, "end": 12}]),
            "1\n00:00:00,500 --> 00:00:02,000\naap kaise hain?\n",
        )

    def test_original_hindi_track_beats_english_translation(self):
        original = [{"url": "original", "ext": "json3"}]
        translation = [{"url": "translated", "ext": "json3"}]
        self.assertEqual(original_caption_formats({
            "subtitles": {"en": translation},
            "automatic_captions": {"en": translation, "hi-orig": original},
        }, ["en", "en-US"]), original)
