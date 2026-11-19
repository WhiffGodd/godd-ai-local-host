import unittest
from unittest.mock import patch

import numpy as np

from ai_video import ExplainerError, _validate_plan, plan_video, render_explainer, validate_generation
from bearing_mechanism import (
    BALL_COUNT, BALL_RADIUS, CENTER_Y, INNER_SPEED, PITCH_RADIUS,
    bearing_angles, bearing_transforms, spacing_storyboard,
)
from cinematic_render import Shot
from explainer_templates import MOTION_TEMPLATE, TEMPLATES


class WorkingMechanismTests(unittest.TestCase):
    def test_spacing_prompt_uses_the_reviewed_sequence_and_preserves_requested_hook(self):
        prompt = 'Explain how a ball bearing cage keeps balls spaced. Open with "What stops these balls bunching together?"'
        with patch("ai_video._request_storyboard") as model:
            template,_,_,scenes = plan_video(prompt,None)
        model.assert_not_called()
        self.assertEqual(template,TEMPLATES["ball-bearing"])
        self.assertEqual(scenes[0]["narration"],"What stops these balls bunching together?")
        self.assertIn("A cage keeps each ball",scenes[1]["narration"])
        self.assertEqual([scene["view"] for scene in scenes],
                         ["wide","exploded","inner-race","rolling-balls","cage","cutaway","wide"])
        self.assertIsNone(spacing_storyboard("Explain how lubrication affects bearing cage wear."))
        self.assertIsNone(spacing_storyboard("Explain why a bicycle freewheel clicks."))
        longer = spacing_storyboard(prompt,True)
        self.assertEqual(len(_validate_plan(longer,"bearing",8)[2]),9)

    def test_narration_rejects_the_observed_cage_speed_error_and_repetition(self):
        lines = [
            "A cage keeps each ball in its own pocket and maintains the gaps between neighbouring balls.",
            "The inner ring turns with the shaft while the outer ring remains fixed in the housing.",
            "Each ball spins about its own centre as that centre travels around the grooved raceway.",
            "The cage travels with the ball centres and turns more slowly than the inner ring.",
            "Together these components carry the load through rolling contact and allow the shaft to turn.",
        ]
        plan = {"title":"How a bearing cage works","hook":"Why don't these balls crash together?",
                "hook_view":"wide","description":"A working bearing explanation.","hashtags":["#Mechanisms"],
                "scenes":[{"heading":"Bearing mechanism","caption":line,"narration":line,"view":"wide"}
                          for line in lines]}
        _validate_plan(plan,"bearing")
        wrong = {**plan,"scenes":[dict(scene) for scene in plan["scenes"]]}
        wrong["scenes"][3]["narration"] = "The cage travels more slowly than the balls so that they remain spaced apart."
        with self.assertRaisesRegex(ValueError,"same orbital speed"):
            _validate_plan(wrong,"bearing")
        repeated = {**plan,"scenes":[dict(scene) for scene in plan["scenes"]]}
        repeated["scenes"][2]["narration"] = lines[1]
        with self.assertRaisesRegex(ValueError,"repeats whole explanations"):
            _validate_plan(repeated,"bearing")

    def test_known_mechanisms_never_use_the_old_photo_motion_default(self):
        prompts = {
            "ball-bearing":"Explain why the balls in a ball bearing stay evenly spaced.",
            "gear-train":"Explain how meshing gears change direction.",
            "piston-and-crank":"Explain how a piston and crank convert reciprocating motion.",
            "pulley-system":"Explain how a fixed pulley redirects a pull.",
            "disc-brake":"Explain how disc brakes slow a rotor.",
            "freewheel-cutaway":"Explain how a bicycle freewheel clicks while coasting.",
            "hydraulic-lift":"Explain how a hydraulic lift raises a load.",
        }
        for selected,prompt in prompts.items():
            for template in ("auto",selected):
                with self.subTest(template=template,topic=selected):
                    payload = validate_generation({"prompt":prompt,"template":template,"visual_style":"motion"})
                    with patch("ai_video.plan_video",side_effect=ExplainerError("Planner reached")) as planner:
                        with self.assertRaisesRegex(ExplainerError,"Planner reached"):
                            render_explainer(payload)
                    self.assertNotEqual(planner.call_args.args[1],MOTION_TEMPLATE)
                    if template != "auto":
                        self.assertEqual(planner.call_args.args[1],TEMPLATES[selected])

    def test_ball_contact_velocities_match_both_races(self):
        step = .0001
        inner,cage,ball = bearing_angles(step)
        centre_speed = cage/step*PITCH_RADIUS
        spin_speed = ball/step*BALL_RADIUS
        # Outer contact is stationary; inner contact follows the inner race.
        self.assertAlmostEqual(centre_speed+spin_speed,0.,places=10)
        self.assertAlmostEqual(centre_speed-spin_speed,INNER_SPEED*(PITCH_RADIUS-BALL_RADIUS),places=10)
        self.assertGreater(cage,0.)
        self.assertLess(cage,inner)
        self.assertLess(ball,0.)

    def test_ball_centres_stay_on_the_raceway_without_colliding(self):
        previous_spin = None
        for time in (0.,.35,1.,5.):
            transforms = bearing_transforms(time)
            centres = np.array([transforms[f"ball{i}"][:3,3] for i in range(BALL_COUNT)])
            radii = np.linalg.norm(centres[:,:2]-[0.,CENTER_Y],axis=1)
            np.testing.assert_allclose(radii,PITCH_RADIUS)
            distances = np.linalg.norm(centres[:,None,:]-centres[None,:,:],axis=2)
            distances += np.eye(BALL_COUNT)*100
            self.assertGreater(distances.min(),2*BALL_RADIUS)
            np.testing.assert_array_equal(transforms["outer"],np.eye(4))
            spin = transforms["ball0"][:3,:3]
            if previous_spin is not None:
                self.assertFalse(np.allclose(spin,previous_spin))
            previous_spin = spin

    def test_inspection_transition_preserves_the_operating_pose_and_camera(self):
        before = Shot("bearing","wide",(180,320),offset=1.)
        following = Shot("bearing","exploded",(180,320),offset=3.,previous_view="wide")
        objects,eye,focus = before.at(2.)
        after,next_eye,next_focus = following.at(0.)
        self.assertEqual(len(objects),len(after))
        for a,b in zip(objects,after):
            self.assertEqual((a[0],a[3]),(b[0],b[3]))
            np.testing.assert_allclose(a[2],b[2])
        np.testing.assert_allclose(eye,next_eye)
        np.testing.assert_allclose(focus,next_focus)
        moved,end_eye,_ = following.at(1.)
        self.assertFalse(np.allclose(end_eye,eye))
        inner = next(item[2] for item in moved if item[0]=="bearing-inner")
        self.assertLess(inner[2,3],-.3)

    def test_spoken_part_changes_do_not_snap_the_camera_to_another_view(self):
        from explainer_parts import PARTS
        shot = Shot("gears","gear-ratio",(180,320))
        _,eye,focus = shot.at(1.,PARTS["gears"][0])
        _,next_eye,next_focus = shot.at(1.,PARTS["gears"][2])
        np.testing.assert_allclose(eye,next_eye)
        np.testing.assert_allclose(focus,next_focus)


if __name__ == "__main__":
    unittest.main()
