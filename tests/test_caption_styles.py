import unittest
from caption_styles import generate_ass


class CaptionStyleTests(unittest.TestCase):
    def test_spoken_word_is_highlighted_without_changing_cue_duration(self):
        words = [{'word': 'make', 'start': 10, 'end': 10.5},
                 {'word': 'it', 'start': 10.5, 'end': 11},
                 {'word': 'count', 'start': 11, 'end': 11.5}]
        ass = generate_ass('1\n00:00:00,000 --> 00:00:01,500\nmake it count\n'.replace('\\n', '\n'), 'beast', words, 10)
        self.assertIn('PlayResY: 1920', ass)
        self.assertIn('Arial Black,56', ass)
        self.assertIn(r'{\c&H56DEFF&\fscx106\fscy106}MAKE', ass)
        self.assertIn('0:00:01.50', ass)

    def test_caption_text_cannot_inject_ass_overrides(self):
        ass = generate_ass('1\n00:00:00,000 --> 00:00:01,000\n{\\p1}test\n'.replace('\\n', '\n'), 'source')
        self.assertIn('｛＼p1｝test', ass)

    def test_neon_and_editorial_presets_include_graphic_layers(self):
        for preset in ('rose', 'cyber', 'cinematic'):
            ass = generate_ass('1\n00:00:00,000 --> 00:00:01,000\nHello world\n'.replace('\\n', '\n'), preset)
            self.assertIn(r'\p1', ass)
            self.assertIn('Dialogue: 0,', ass)
            self.assertIn('Dialogue: 1,', ass)
