import json
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from ai_video import ExplainerError, _EXAMPLE, plan_video, render_explainer, validate_generation
from explainer_templates import MOTION_TEMPLATE
from motion_graphics import MotionReel, _pose, extract_cutout, motion_plan_from_scenes, read_motion_plan
from explainer_photos import photo_credit


def plan_rows():
    rows = [("ball","center","medium","slide-left"),("ball","right","medium","lift"),
            ("cup","center","large","pulse"),("spring","center","medium","rotate"),
            ("ball","upper","small","lower"),("ball","center","medium","hold")]
    return {"assets":[{"name":"ball","description":"one round red rubber ball"},
                      {"name":"cup","description":"one small blue ceramic cup"},
                      {"name":"spring","description":"one steel coil spring"}],
            "scenes":[{"layers":[dict(zip(("asset","position","size","action"),row))]} for row in rows]}


class MotionGraphicsTests(unittest.TestCase):
    def test_custom_prompt_and_narration_reach_the_motion_planner(self):
        sample = plan_rows()
        assets = {asset["name"]:asset for asset in sample["assets"]}
        objects = [[{**assets[layer["asset"]],**{key:layer[key] for key in ("position","size","action")},"avoid":""}
                    for layer in scene["layers"]] for scene in sample["scenes"]]
        board = {**_EXAMPLE,"template":"motion","hook_objects":objects[0],
                 "scenes":[{**scene,"view":"wide","objects":objects[index+1]}
                           for index,scene in enumerate(_EXAMPLE["scenes"])]}
        prompt = "Explain how a spring launches a ball."
        with patch("ai_video._request_storyboard",return_value=json.dumps(board)) as request:
            _,_,_,scenes = plan_video(prompt,MOTION_TEMPLATE)
            plan = motion_plan_from_scenes(scenes)
        self.assertIn(prompt,request.call_args.args[0])
        self.assertEqual(scenes[1]["objects"],objects[1])
        self.assertEqual(len(plan[1]),6)
        broken = plan_rows()
        broken["scenes"] = broken["scenes"][:-1]
        with self.assertRaises(ValueError):
            read_motion_plan(broken,6)

    def test_shared_object_and_background_are_continuous_across_scene_boundary(self):
        plan = read_motion_plan(plan_rows(),6)
        pictures = {asset.name:Image.new("RGBA",(80,80),(218,122,46,255)) for asset in plan[0]}
        scenes = [{"heading":"A moving object"} for _ in range(6)]
        reel = MotionReel(plan,pictures,scenes,(180,320))
        before = reel.frame(0,1.,None)
        after = reel.frame(1,0.,None)
        self.assertEqual(before.tobytes(),after.tobytes())
        self.assertNotEqual(after.tobytes(),reel.frame(1,.6,None).tobytes())
        layer = plan[1][1][0]
        first,last = _pose(layer,0),_pose(layer,1)
        self.assertLess(abs(_pose(layer,.001)[1]-first[1]),.0001)
        self.assertLess(abs(_pose(layer,.999)[1]-last[1]),.0001)

    def test_cutout_retains_the_object_and_removes_the_backdrop(self):
        class Session:
            def get_inputs(self):
                return [type("Input",(),{"name":"image"})()]
            def run(self,*_):
                mask = np.zeros((1,1,320,320),dtype=np.float32)
                mask[:,:,70:250,70:250] = 1.
                return [mask]
        picture = Image.new("RGB",(320,320),"white")
        picture.paste("red",(70,70,250,250))
        with patch("motion_graphics._segmentation_session",return_value=Session()):
            cutout = extract_cutout(picture)
        self.assertLess(cutout.width,200)
        self.assertEqual(cutout.getpixel((cutout.width//2,cutout.height//2))[:3],(255,0,0))
        self.assertLess(cutout.getchannel("A").getpixel((0,0)),128)

    def test_motion_style_uses_the_prompt_through_the_normal_render_entry_point(self):
        payload = validate_generation({"prompt":"Explain why popcorn pops.","visual_style":"motion"})
        with patch("ai_video.plan_video",side_effect=ExplainerError("Planner reached")) as planner:
            with self.assertRaisesRegex(ExplainerError,"Planner reached"):
                render_explainer(payload)
        self.assertEqual(planner.call_args.args[1],MOTION_TEMPLATE)
        with self.assertRaises(ValueError):
            validate_generation({"prompt":"Explain popcorn.","visual_style":"unknown"})

    def test_sourced_photo_credit_keeps_author_source_license_and_changes(self):
        page = {"title":"File:Example.jpg"}
        info = {"descriptionurl":"https://commons.wikimedia.org/wiki/File:Example.jpg",
                "extmetadata":{"LicenseUrl":{"value":"https://creativecommons.org/licenses/by/4.0/"},
                               "LicenseShortName":{"value":"CC BY 4.0"},"Artist":{"value":"<b>Example artist</b>"}}}
        credit = photo_credit(page,info)
        self.assertIn("Example artist",credit)
        self.assertIn("background removed and animated",credit)
        self.assertIn("https://creativecommons.org/licenses/by/4.0/",credit)
        info["extmetadata"]["LicenseUrl"]["value"] = "https://creativecommons.org/licenses/by-sa/4.0/"
        self.assertIsNone(photo_credit(page,info))

    def test_airflow_is_animated_without_generating_an_abstract_object_image(self):
        data = {"assets":[{"name":"Warm air","description":"Air rising around the visible object","kind":"airflow"}],
                "scenes":[{"layers":[{"asset":"Warm air","position":"center","size":"large","action":"hold"}]}
                          for _ in range(3)]}
        plan = read_motion_plan(data,3)
        reel = MotionReel(plan,{},[{"heading":"Air rises"}]*3,(180,320))
        self.assertNotEqual(reel.frame(1,.3,None).tobytes(),reel.frame(1,.6,None).tobytes())

    def test_narrated_process_effect_follows_its_moving_object(self):
        item = {"name":"Balloon","description":"A complete hot air balloon", "avoid":"",
                "kind":"object","position":"center","size":"large","action":"lift","effect":"heat"}
        assets,shots = motion_plan_from_scenes([{"objects":[item]}]*3)
        self.assertEqual([asset.kind for asset in assets],["object","heat"])
        for progress in (0.,.3,.9,1.):
            self.assertEqual(_pose(shots[1][0],progress),_pose(shots[1][1],progress))
        pictures = {"Balloon":Image.new("RGBA",(80,80),(100,100,100,255))}
        reel = MotionReel((assets,shots),pictures,[{"heading":"Heat rises"}]*3,(180,320))
        rendered = np.array(reel.frame(1,.5,None))
        self.assertGreater(int(rendered[:,:,0].max()),200)


if __name__ == "__main__":
    unittest.main()
