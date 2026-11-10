import unittest
from api.clip_boundaries import snap_to_clean_sentence_boundaries as snap
from analyzer import analyze_virality_and_cut_clips
from api.analyzer import analyze_virality_and_cut_clips as hosted_analyze


def seg(start, end, text):
    return {"start": start, "end": end, "text": text}


class ClipBoundaryTests(unittest.TestCase):
    def test_extend_past_85_to_finish_answer(self):
        transcript = [seg(0, 8, "How do you make this work?"),
                      seg(8, 40, "Start with the basic system."),
                      seg(40, 60, "For example, configure the inputs."),
                      seg(60, 84, "And then check the outputs."),
                      seg(84, 108, "Because these checks are what make the system reliable."),
                      seg(110, 130, "Next question, what does it cost?")]
        start, end, included = snap(transcript, 0)
        self.assertEqual(start, 0)
        self.assertGreaterEqual(end, 108)
        self.assertLess(end, 110)
        self.assertEqual(included[-1], transcript[4])

    def test_question_is_not_an_answer_ending(self):
        t = [seg(0, 40, "Why does this happen?"), seg(40, 78, "The input is missing a required value."),
             seg(80, 90, "Next question, how can we prevent it?")]
        self.assertGreaterEqual(snap(t, 0)[1], 78)

    def test_incomplete_candidates_are_rejected_not_just_penalized(self):
        t = [seg(0, 40, "You need to start with the"), seg(40, 84, "and then you must"),
             seg(84, 190, "because the full explanation keeps going")]
        self.assertEqual(snap(t, 0)[2], [])

    def test_unpunctuated_lowercase_captions_use_pause(self):
        t = [seg(0, 30, "the first step is to check your setup"),
             seg(30, 70, "the result is a reliable configuration"),
             seg(72, 90, "moving on to the next question")]
        self.assertEqual(snap(t, 0)[2][-1], t[1])

    def test_does_not_enter_next_utterance_with_tail_padding(self):
        t = [seg(0, 58, "The complete answer."), seg(58.1, 200, "An unrelated long discussion")]
        self.assertLess(snap(t, 0)[1], 58.1)

    def test_chapter_and_video_limits_are_respected(self):
        t = [seg(0, 50, "The first complete point."), seg(50, 100, "Another complete point."),
             seg(102, 150, "Moving on to another topic.")]
        self.assertLessEqual(snap(t, 0, boundary_limit=75)[1], 75)
        self.assertLessEqual(snap(t, 0, boundary_limit=100)[1], 100)

    def test_no_forced_cut_when_completion_exceeds_hard_limit(self):
        t = [seg(0, 80, "The explanation continues because"), seg(80, 200, "the details take a long time.")]
        self.assertEqual(snap(t, 0)[2], [])
        self.assertEqual(analyze_virality_and_cut_clips(t, 200, "Example"), [])

    def test_local_and_hosted_analysis_accept_long_complete_answer(self):
        t = [seg(0, 8, "How does the system work?"), seg(8, 40, "First prepare the input."),
             seg(40, 60, "And then validate the schema."), seg(60, 84, "Because valid input matters."),
             seg(84, 108, "That's why the system produces reliable results."),
             seg(110, 130, "Next question, how much does it cost?")]
        for analyze in (analyze_virality_and_cut_clips, hosted_analyze):
            with self.subTest(analyze=analyze.__module__):
                clips = analyze(t, 130, "How systems work")
                self.assertTrue(clips)
                self.assertGreaterEqual(clips[0]["end"], 108)
                self.assertAlmostEqual(clips[0]["duration_sec"], clips[0]["end"] - clips[0]["start"], delta=.11)


if __name__ == "__main__":
    unittest.main()
