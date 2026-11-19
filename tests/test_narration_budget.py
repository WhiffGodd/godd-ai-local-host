import unittest
from unittest.mock import patch

from ai_video import FPS, _shorten_narration, render_explainer, validate_generation
from explainer_templates import TEMPLATES
from narration_budget import compact_sentences, word_count


def scenes():
    rows = [
        ("Input gear","The input gear rotates when the motor turns it. Its teeth pass motion to the next gear. A close view helps you follow the contact."),
        ("Idler gear","The idler gear transfers rotation to the next wheel. It reverses the direction at this contact. The teeth stay engaged as the mechanism turns."),
        ("Output gear","The output gear receives the motion through its teeth. Its size changes the rotation speed relative to the input gear. The shaft carries this motion onward."),
        ("Connected teeth","The teeth keep the gears connected during rotation. Each tooth pushes the next gear along. These connections continue throughout the operating cycle."),
        ("Complete mechanism","The full mechanism transfers the input motion to the output shaft. All the gears remain connected. That completes the path from the motor to the output."),
    ]
    return [{"heading":"How do these gears move together?","narration":"How do these gears move together?","view":"wide","opening":True},
            *[{"heading":heading,"narration":text,"caption":heading+".","view":"gear-ratio"} for heading,text in rows]]


class NarrationBudgetTests(unittest.TestCase):
    def test_compaction_keeps_every_scene_whole_sentences_and_the_payoff(self):
        original = scenes()
        result = compact_sentences(original,100)
        self.assertIsNotNone(result)
        self.assertLessEqual(word_count(result),100)
        self.assertEqual(len(result),len(original))
        self.assertEqual(result[0],original[0])
        self.assertTrue(result[-1]['narration'].endswith('That completes the path from the motor to the output.'))
        for before,after in zip(original[1:],result[1:]):
            self.assertEqual(before['view'],after['view'])
            for sentence in after['narration'].split('. '):
                self.assertIn(sentence,before['narration'])

    def test_single_sentences_that_cannot_fit_are_rewritten_instead_of_cut(self):
        original = scenes()
        for scene in original[1:]:
            scene['narration'] = scene['narration'].replace('.','')+'.'
        self.assertIsNone(compact_sentences(original,50))
        lines = [
            'The motor turns the input gear.',
            'The idler gear transfers the rotation.',
            'The output gear drives its shaft.',
            'The teeth stay engaged during rotation.',
            'The complete mechanism transfers motion to the output.',
        ]
        import json
        with patch('ai_video._request_storyboard',return_value=json.dumps({'narrations':lines})):
            result = _shorten_narration(original,50,'gears')
        self.assertLessEqual(word_count(result),50)
        self.assertEqual([row['view'] for row in result],[row['view'] for row in original])
        self.assertEqual(result[-1]['narration'],lines[-1])

    def exercise_render(self,durations):
        script = scenes()
        counts = []
        for duration in durations:
            frames = [3*FPS]+[round((duration-3)*FPS/5)]*5
            counts.append((frames,[[] for _ in script],[[] for _ in script]))
        class VerifiedNarration(RuntimeError):
            pass
        with patch('ai_video.plan_video',return_value=(TEMPLATES['gear-train'],'Gears','Description',script)) as planner, \
             patch('ai_video._continuous_narration',side_effect=counts) as voice, \
             patch('ai_video.CinematicRenderer',side_effect=VerifiedNarration('Narration fitted')):
            with self.assertRaisesRegex(VerifiedNarration,'Narration fitted'):
                render_explainer(validate_generation({'prompt':'Explain a gear train.','max_seconds':90}))
        return planner,voice

    def test_complete_shorter_video_does_not_get_expanded_toward_ninety_seconds(self):
        planner,voice = self.exercise_render([52])
        planner.assert_called_once()
        self.assertEqual(voice.call_count,1)

    def test_overlong_take_is_shortened_and_retimed_without_replanning_the_mechanism(self):
        planner,voice = self.exercise_render([125,84])
        planner.assert_called_once()
        self.assertEqual(voice.call_count,2)
        original = voice.call_args_list[0].args[0]
        revised = voice.call_args_list[1].args[0]
        self.assertLess(word_count(revised),word_count(original))
        self.assertEqual(len(revised),len(original))
        self.assertTrue(revised[-1]['narration'].endswith('That completes the path from the motor to the output.'))


if __name__=='__main__':
    unittest.main()
