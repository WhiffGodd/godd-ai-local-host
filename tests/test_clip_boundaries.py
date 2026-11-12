import unittest
from api.clip_boundaries import snap_to_clean_sentence_boundaries as snap
from api.clip_boundaries import select_short_clip_windows
from api.clip_metadata import add_clip_metadata
from analyzer import analyze_virality_and_cut_clips
from api.analyzer import analyze_virality_and_cut_clips as hosted_analyze


def seg(start, end, text):
    return {"start": start, "end": end, "text": text}


class ClipBoundaryTests(unittest.TestCase):
    def test_clip_metadata_uses_source_context_and_a_time_in_the_clip(self):
        clip = {"start": 20, "end": 95, "title": "Late-round clutch 🔥",
                "full_text": "He holds the site until the other players arrive."}
        add_clip_metadata([clip], "Valorant ranked gameplay", "Example creator",
                          "https://www.youtube.com/watch?v=abcdefghijk")
        self.assertEqual(clip["hashtags"], ["#Valorant", "#Gaming", "#Shorts"])
        self.assertIn("Example creator", clip["description"])
        self.assertIn("https://www.youtube.com/watch?v=abcdefghijk", clip["description"])
        self.assertIn("#Valorant", clip["description"])
        self.assertGreater(clip["thumbnail_time"], clip["start"])
        self.assertLess(clip["thumbnail_time"], clip["end"])

    def test_gaming_banter_does_not_add_unrelated_hashtags(self):
        clip = {"start": 20, "end": 95, "title": "Game two: Fracture conclusion",
                "full_text": "I don't think we're cooking okay we need to be walking up with our team"}
        add_clip_metadata([clip], "This INDIAN SILVER Says He Deserves ASCENDANT")
        self.assertEqual(clip["hashtags"], ["#Valorant", "#Gaming", "#Shorts"])

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

    def test_follow_up_beats_mid_answer_pause_and_trims_rolling_caption(self):
        t = [seg(0, 8, "How do you earn people's trust?"),
             seg(8, 55, "The first step is to listen carefully."),
             seg(48, 83, "Give people space to finish before sharing your perspective."),
             seg(83, 113, "I mean, do this consistently, especially in difficult conversations."),
             {**seg(110, 117, "Trust builds over time. How do you"),
              "words": [{"word": word, "start": start} for word, start in zip(
                  "Trust builds over time. How do you".split(),
                  (110, 110.5, 111, 111.5, 112.25, 113, 114))]},
             seg(115, 119, "repair it after a mistake?"),
             seg(120, 140, "Start by acknowledging what went wrong.")]
        for analyze in (analyze_virality_and_cut_clips, hosted_analyze):
            with self.subTest(analyze=analyze.__module__):
                clip = analyze(t, 140, "Trust")[0]
                self.assertEqual(clip["end"], 112.25)
                self.assertTrue(clip["full_text"].endswith("Trust builds over time."))
        chapter = [{"start_time": 0, "title": "Trust"},
                   {"start_time": 120, "title": "Repair"}]
        clip = analyze_virality_and_cut_clips(t, 140, "Trust", chapter)[0]
        self.assertEqual(clip["end"], 112.25)
        self.assertNotIn("How do you", clip["video_subtitles"][-1]["text"])
        self.assertLessEqual(clip["subtitles"][-1]["end"], clip["end"])

    def test_rhetorical_question_and_pause_do_not_end_answer(self):
        t = [seg(0, 8, "How do you earn people's trust?"),
             seg(8, 48, "Start by listening carefully."),
             seg(50, 58, "What is the most common mistake?"),
             seg(58, 90, "I mean, we often jump in before the other person can finish."),
             seg(90, 118, "It takes practice to give people room to speak."),
             seg(120, 128, "How can you rebuild trust after a mistake?"),
             seg(128, 140, "Start with an honest apology.")]
        self.assertEqual(snap(t, 0)[1], 120)
        self.assertEqual(snap(t, 0, boundary_limit=110)[2], [])

    def test_no_captions_does_not_propose_unverified_clips(self):
        for analyze in (analyze_virality_and_cut_clips, hosted_analyze):
            self.assertEqual(analyze([], 600, "Trust"), [])

    def test_both_analyzers_find_multiple_short_excerpts_in_one_chapter(self):
        t = [seg(0, 20, "An emergency fund protects your monthly budget."),
             seg(20, 60, "Start by saving a small amount each month."),
             seg(60, 70, "That's how you make the habit sustainable."),
             seg(72, 76, "Moving on to a new subject."),
             seg(80, 100, "Compound interest rewards people who start early."),
             seg(100, 140, "Small contributions can grow substantially over time."),
             seg(140, 151, "That's why consistent saving makes such a difference.")]
        windows = select_short_clip_windows(t, 151, [(0, 151)])
        self.assertEqual([(start, end) for start, end, _ in windows], [(0, 70.12), (80, 151)])
        for analyze in (analyze_virality_and_cut_clips, hosted_analyze):
            with self.subTest(analyze=analyze.__module__):
                clips = analyze(t, 151, "Saving habits")
                self.assertEqual(len(clips), 2)
                self.assertTrue(all(60 <= clip["duration_sec"] <= 90 for clip in clips))

    def test_short_excerpt_can_start_and_end_inside_rolling_cues(self):
        t = [{**seg(0, 15, "It was a long day. A checklist makes work easier."),
              "words": [{"word": word, "start": index * .5, "end": (index + 1) * .5}
                        for index, word in enumerate("It was a long day. A checklist makes work easier.".split())]},
             seg(12, 59, "Use a checklist to verify each step before handing work off."),
             {**seg(68, 80, "That's how teams avoid repeat mistakes. Next question, how do teams stay organized?"),
              "words": [{"word": word, "start": 68 + index * .5, "end": 68 + (index + 1) * .5}
                        for index, word in enumerate(
                            "That's how teams avoid repeat mistakes. Next question, how do teams stay organized?".split())]}]
        start, end, included = select_short_clip_windows(t, 80)[0]
        self.assertEqual((start, end), (2.5, 71.0))
        self.assertEqual(included[0]["text"], "A checklist makes work easier.")
        self.assertEqual(included[-1]["text"], "That's how teams avoid repeat mistakes.")

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
        t = [seg(0, 80, "The explanation continues because"), seg(80, 130, "the details take a long time.")]
        self.assertEqual(snap(t, 0, completion_limit=180)[2], [])
        self.assertEqual(analyze_virality_and_cut_clips(t, 130, "Example"), [])

    def test_plain_captions_find_clips_between_measured_restarts(self):
        t = [{**seg(0, 8, "we won the first round"), "words": [{"word": "round", "end": 4}]},
             seg(6, 40, "okay lets set up for a retake"),
             {**seg(40, 78, "they held the site and won the round"), "words": [{"word": "round", "end": 73}]},
             seg(76, 90, "all right lets check the score")]
        for analyze in (analyze_virality_and_cut_clips, hosted_analyze):
            with self.subTest(analyze=analyze.__module__):
                clip = analyze(t, 90, "Match recap")[0]
                self.assertEqual((clip["start"], clip["end"]), (6, 73.18))
                self.assertTrue(clip["full_text"].endswith("won the round"))

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
