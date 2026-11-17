import json
import os
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from pathlib import Path
import requests
from PIL import Image
from unittest.mock import patch
from server import ThreadedHTTPServer, GoddAIRequestHandler, validate_render_payload
from render_jobs import RenderJobs
from ai_video import FPS, ExplainerError, _EXAMPLE, _fit_runtime, _part_schedule, _plan_mechanism, _validate_plan, plan_video, render_explainer, validate_generation
from ai_video import _subtitle_phrases, _subtitle_schedule
from cinematic_render import Shot, _part_badge
from explainer_parts import part_mentions
from explainer_templates import GENERATED_TEMPLATE, MECHANISM_TEMPLATE, TEMPLATES, matching_subjects
from procedural_scene import StageShot, read_actions, read_stage
from explainer_visuals import IllustratedShot, LocalVisualEngine
from mechanism_animation import MechanismShot, _transform


class PublicHostingTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadedHTTPServer(('127.0.0.1', 0), GoddAIRequestHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def test_only_public_application_assets_are_served(self):
        for path in ('/', '/app.js', '/style.css', '/youtube-studio.js', '/privacy.html',
                     '/ai-videos.html', '/ai-videos.js', '/ai-videos.css'):
            with urllib.request.urlopen(self.url + path) as response:
                self.assertEqual(response.status, 200)
        for path in ('/.git/config', '/server.py', '/.env', '/../server.py', '/public/speech_accuracy_check.json'):
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(self.url + path)
            self.assertEqual(error.exception.code, 404)

    def test_ai_video_template_catalog_and_seekable_preview(self):
        with patch("server.generation_settings", return_value={"available": False}):
            with urllib.request.urlopen(self.url + "/api/ai-videos/templates") as response:
                catalog = json.load(response)
        self.assertEqual({template["id"] for template in catalog["templates"]}, set(TEMPLATES))
        for template in catalog["templates"]:
            with urllib.request.urlopen(self.url + template["poster"]) as response:
                self.assertEqual(response.read(4), b"RIFF")
            with urllib.request.urlopen(self.url + template["preview"]) as response:
                self.assertEqual(response.headers.get_content_type(), "video/webm")
                self.assertEqual(response.read(4), b"\x1a\x45\xdf\xa3")

        with tempfile.TemporaryDirectory() as tmp:
            output = os.path.join(tmp, "preview.mp4")
            with open(output, "wb") as stream:
                stream.write(b"example MP4 data")
            rendering = threading.Event()
            finish = threading.Event()

            def render(payload, report_progress):
                self.assertEqual(payload["max_seconds"], 90)
                report_progress("rendering", 40)
                rendering.set()
                if not finish.wait(5):
                    raise RuntimeError("Preview test did not release the render")
                return output, {"title": "A test explainer", "description": "#Shorts"}

            manager = RenderJobs(render, report_progress=True)
            with patch("server.AI_VIDEO_JOBS", manager):
                request = urllib.request.Request(
                    self.url + "/api/ai-videos", data=b'{"template":"bicycle-drivetrain","example":true,"max_seconds":90}',
                    headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(request) as response:
                    self.assertEqual(response.status, 202)
                    job_id = json.load(response)["id"]
                source = self.url + f"/api/ai-videos/{job_id}"
                try:
                    self.assertTrue(rendering.wait(3))
                    with urllib.request.urlopen(source) as response:
                        job = json.load(response)
                    self.assertEqual(job["state"], "rendering")
                    self.assertEqual(job["progress"], {"stage": "rendering", "percent": 40})
                    with self.assertRaises(urllib.error.HTTPError) as error:
                        urllib.request.urlopen(source + "/video")
                    self.assertEqual(error.exception.code, 409)
                finally:
                    finish.set()
                manager.pending.join()
                with urllib.request.urlopen(source) as response:
                    job = json.load(response)
                self.assertEqual(job["metadata"]["title"], "A test explainer")
                self.assertNotIn("progress", job)
                request = urllib.request.Request(source + "/video?download=1", headers={"Range": "bytes=8-10"})
                with urllib.request.urlopen(request) as response:
                    self.assertEqual(response.status, 206)
                    self.assertEqual(response.headers["Content-Range"], "bytes 8-10/16")
                    self.assertEqual(response.headers["Content-Disposition"], 'attachment; filename="A_test_explainer.mp4"')
                    self.assertEqual(response.read(), b"MP4")

    def test_explainer_hook_precedes_the_complete_story_and_voice_is_validated(self):
        _, _, scenes = _validate_plan(_EXAMPLE, "bicycle")
        self.assertEqual(scenes[0]["heading"], _EXAMPLE["hook"])
        self.assertEqual(scenes[0]["narration"], _EXAMPLE["hook"])
        self.assertTrue(scenes[0]["opening"])
        self.assertEqual([scene["narration"] for scene in scenes[1:]],
                         [scene["narration"] for scene in _EXAMPLE["scenes"]])
        with self.assertRaises(ValueError):
            _validate_plan({**_EXAMPLE, "hook": "Hello"}, "bicycle")
        longer_hook = "You stop moving the pedals, but the wheel keeps turning. What lets it roll without pulling the chain?"
        _, _, longer_scenes = _validate_plan({**_EXAMPLE, "hook": longer_hook}, "bicycle")
        self.assertEqual(longer_scenes[0]["narration"], "You stop moving the pedals, but the wheel keeps turning.")
        with self.assertRaises(ValueError):
            _validate_plan({**_EXAMPLE, "hook_view": "spinning-rotor"}, "bicycle")
        sample = {"template": "bicycle-drivetrain", "example": True}
        self.assertEqual(validate_generation(sample)["voice"], "expressive")
        self.assertEqual(validate_generation({**sample, "voice": "energetic"})["voice"], "energetic")
        with self.assertRaises(ValueError):
            validate_generation({**sample, "voice": "unknown"})
        with self.assertRaises(ValueError):
            validate_generation({**sample, "prompt": "Explain how the Moon goes around Earth."})

    def test_bicycle_topic_uses_the_typed_prompt_even_when_it_matches_the_example(self):
        prompt = "Explain how bicycle pedals turn the rear wheel through the crank, chain and rear cog."
        with patch("ai_video.plan_video", side_effect=ExplainerError("Prompt reached the planner")) as planner:
            with self.assertRaisesRegex(ExplainerError, "Prompt reached the planner"):
                render_explainer(validate_generation({"prompt": prompt}))
            self.assertEqual(planner.call_args.args[0], prompt)

    def test_explainer_skips_rephrased_hook_but_keeps_first_new_fact(self):
        hook = "How can the rear wheel keep spinning while the pedals stand still?"
        fresh = "Inside the rear hub, the freewheel disengages and lets the wheel turn on its own."
        opening = {**_EXAMPLE["scenes"][0], "caption": hook,
                   "narration": "How does the rear wheel keep spinning while the pedals stand still? " + fresh}
        doubled_hook = hook + " What keeps that same wheel moving?"
        _, _, scenes = _validate_plan({**_EXAMPLE, "hook": doubled_hook,
                                     "scenes": [opening, *_EXAMPLE["scenes"][1:]]}, "bicycle")
        self.assertEqual([scene["narration"] for scene in scenes[:2]], [hook, fresh])
        self.assertEqual(scenes[1]["caption"], fresh)

    def test_component_callouts_follow_the_parts_named_in_the_narration(self):
        narration = "The caliper moves first. Its brake pads close around the rotor."
        mentions = part_mentions("disc_brake", narration)
        subjects = matching_subjects("How bicycle disc brakes stop the wheel.")
        self.assertEqual([template.id for template in subjects], ["disc-brake"])
        self.assertEqual([part.label for _, part in mentions], ["Caliper", "Brake pads", "Rotor"])
        self.assertEqual(part_mentions("bicycle", narration), [])
        schedule = _part_schedule([(0.1, mentions[0][1]), (0.4, mentions[1][1]), (0.8, mentions[2][1])],
                                  8 * FPS, "caliper-and-pads")
        self.assertEqual([part.label for _, part in schedule], ["Caliper", "Brake pads", "Rotor"])

    def test_narration_subtitles_keep_spoken_words_and_leave_silent_gaps(self):
        narration = "The caliper grips the rotor. The wheel slows as friction turns motion into heat."
        phrases = _subtitle_phrases(narration)
        self.assertEqual(" ".join(text for _, text in phrases), narration)
        self.assertTrue(all(narration[start:].startswith(text) for start, text in phrases))
        captions = [(0.1, 0.3, phrases[0][1]), (0.5, 0.9, phrases[1][1])]
        self.assertEqual(list(_subtitle_schedule(captions,100)), [(10,30,phrases[0][1]), (50,90,phrases[1][1])])
        self.assertEqual(list(_subtitle_schedule(captions,80))[1], (40,72,phrases[1][1]))

    def test_part_labels_stay_in_a_fixed_screen_position(self):
        first, first_position = _part_badge("Rotor", (720,1280))
        second, second_position = _part_badge("Brake pads", (720,1280))
        self.assertEqual(first_position, second_position)
        self.assertNotEqual(first.tobytes(), second.tobytes())

    def test_explainer_runtime_fits_narration_and_scene_boundaries_together(self):
        for seconds, expected in ((44, 50), (50, 50), (55, 55), (60, 60), (66, 60)):
            with self.subTest(seconds=seconds):
                frames, tempo = _fit_runtime([3 * FPS, (seconds - 3) * FPS])
                self.assertEqual(sum(frames), expected * FPS)
                self.assertEqual(tempo, seconds / expected)
                self.assertAlmostEqual(frames[0], 3 * FPS / tempo, delta=0.5)
        for seconds in (25, 90):
            with self.assertRaises(ExplainerError):
                _fit_runtime([seconds * FPS])
        frames, tempo = _fit_runtime([3 * FPS, 93 * FPS], max_seconds=90)
        self.assertEqual(sum(frames), 90 * FPS)
        self.assertEqual(tempo, 96 / 90)
        self.assertEqual(_fit_runtime([70 * FPS], max_seconds=90), ([70 * FPS], 1.0))
        with self.assertRaises(ValueError):
            validate_generation({"example": True, "max_seconds": 91})

    def test_explainer_auto_selects_template_and_keeps_manual_override(self):
        template_id = "gear-train"
        prompt = "Explain why touching gears turn in opposite directions."
        self.assertEqual(validate_generation({"prompt": prompt})["template"], "auto")
        board = {**_EXAMPLE, "title": "Why Gears Turn In Opposite Directions", "template": template_id,
                 "hook_view": "drive-mesh",
                 "scenes": [{**scene, "view": "output-mesh"} for scene in _EXAMPLE["scenes"]]}
        with patch.dict(os.environ, {"AI_VIDEO_GEMINI_API_KEY": ""}), patch("ai_video.requests.post") as post:
            post.return_value.json.return_value = {"message": {"content": json.dumps(board)}}
            template, _, _, scenes = plan_video(prompt, None)
            self.assertEqual(template.id, template_id)
            self.assertEqual(scenes[0]["view"], "drive-mesh")
            self.assertEqual(scenes[1]["view"], "output-mesh")
            format = post.call_args.kwargs["json"]["format"]["properties"]
            self.assertIn(template_id, format["template"]["enum"])
            self.assertNotIn("coasting", format["hook_view"]["enum"])
            template, *_ = plan_video(prompt, TEMPLATES[template_id])
            self.assertEqual(template.id, template_id)
            self.assertEqual(post.call_args.kwargs["json"]["format"]["properties"]["template"]["enum"],
                             [template_id])
            with patch("ai_video._request_storyboard", side_effect=['{"template":"gear-train"}', json.dumps(board)]) as retry:
                self.assertEqual(plan_video(prompt, None)[0].id, template_id)
                self.assertEqual(retry.call_count, 2)

    def test_ai_illustrations_can_be_selected_explicitly(self):
        board = {**_EXAMPLE, "title": "How a Stapler Works", "template": "generated", "hook_view": "wide",
                 "visual_subject": "A brushed-steel desktop stapler", "hook_visual": "A stapler sits above a stack of paper",
                 "scenes": [{**scene, "view": "detail", "visual": "Close-up of the anvil"} for scene in _EXAMPLE["scenes"]]}
        prompt = "Explain how a stapler folds a staple."
        with patch("ai_video._request_storyboard", return_value=json.dumps(board)) as request:
            template, title, _, scenes = plan_video(prompt, GENERATED_TEMPLATE)
        self.assertEqual(template, GENERATED_TEMPLATE)
        self.assertEqual(title, "How a Stapler Works")
        self.assertEqual(request.call_args.args[0], prompt)
        self.assertEqual(scenes[0]["visual_subject"], board["visual_subject"])
        self.assertEqual(scenes[1]["visual"], "Close-up of the anvil")
        self.assertEqual(validate_generation({"prompt": "Toast"})["prompt"], "Toast")
        with patch("ai_video.plan_video", return_value=(template, title, "", scenes)), patch.object(
                LocalVisualEngine, "configured", return_value=None):
            with self.assertRaisesRegex(ExplainerError, "need the local image model"):
                render_explainer(validate_generation({"prompt": prompt}))

    def test_unmatched_prompt_gets_a_continuous_cutaway(self):
        prompt = "Explain how a desktop stapler folds a staple against the anvil."
        board = {**_EXAMPLE, "title": "How a Stapler Works", "template": "mechanism", "hook_view": "wide",
                 "scenes": [{**scene, "view": "detail"} for scene in _EXAMPLE["scenes"]]}
        data = {
            "parts": [
                "Handle|contour|steel|22,40|20,40 75,34 79,38 24,46",
                "Driver|plate|gold|72,47|69,45 75,50",
                "Anvil|plate|dark|74,67|59,65 82,70",
            ],
            "actions": [
                "1|Handle|turn|13,0|.1,.7",
                "2|Driver|move|0,14|.1,.7",
                "3|Driver|move|0,-14|.1,.7",
            ],
        }
        with patch("ai_video._ollama_models", return_value=["qwen3:4b"]), patch(
                "ai_video._request_storyboard", side_effect=[json.dumps(board), json.dumps(data)]) as request:
            template, _, _, scenes = plan_video(prompt, TEMPLATES["ball-bearing"])
            mechanism = _plan_mechanism(prompt, scenes)
        self.assertEqual(template, MECHANISM_TEMPLATE)
        self.assertIn(prompt, request.call_args.args[0])
        parts, actions = mechanism
        driver = tuple(action for action in actions if action.part == "Driver")
        before = _transform(parts[1], driver, 2, 0)[0]
        after = _transform(parts[1], driver, 2, 1)[0]
        self.assertEqual(after, _transform(parts[1], driver, 3, 0)[0])
        self.assertEqual(after[0][1] - before[0][1], 14)
        shot = MechanismShot(mechanism, (180,320), 2)
        self.assertNotEqual(shot.frame(.2,None).tobytes(), shot.frame(.6,None).tobytes())

    def test_illustrated_shot_moves_camera_and_burns_subtitles(self):
        with tempfile.TemporaryDirectory() as directory:
            def render(arguments, **_):
                picture = Image.new("RGB", (90, 160), "black")
                picture.paste("red", (8,12,28,65))
                picture.save(arguments[arguments.index("-o")+1])
                self.assertIn("stainless steel toaster", arguments[arguments.index("-p")+1])
            engine = LocalVisualEngine("sd-cli-test", Path("model.safetensors"), "cpu")
            with patch("explainer_visuals.subprocess.run", side_effect=render):
                picture = engine.generate("stainless steel toaster", {"visual":"bread in the slots"}, Path(directory), 0)
        shot = IllustratedShot(picture, (90,160), 0, "wide")
        first, last = shot.frame(0,None), shot.frame(1,None)
        self.assertNotEqual(first.tobytes(), last.tobytes())
        overlay = Image.new("RGBA",(9,6),"white")
        self.assertEqual(shot.frame(0,(overlay,(2,120))).getpixel((3,121)), (255,255,255))

    def test_procedural_stage_moves_attached_objects(self):
        scene = {"label":"Heating coil", "shape":"ring", "color":"red", "pose":"front", "motion":"pulse",
                 "position":[0., .5, 0.], "size":[.4, .4, .3]}
        _, _, scenes = _validate_plan(_EXAMPLE, "bicycle")
        storyboard = {"objects":[scene, {**scene, "label":"Bread", "shape":"box", "motion":"still",
                                       "relation":"on-top", "anchor":"Heating coil"}],
                      "actions":[{"beat":1,"part":"Heating coil","direction":"up","distance":1,
                                  "turn":0,"start":.2,"end":.8}]}
        stage = read_stage(storyboard)
        actions = read_actions(storyboard, stage, scenes)
        self.assertEqual([item.label for item in stage], ["Heating coil", "Bread"])
        self.assertGreater(stage[1].position[1], stage[0].position[1])
        shot = StageShot(stage,"wide",None,actions=actions,beat=1,duration=10.)
        start, _, _ = shot.at(1.)
        end, _, _ = shot.at(9.)
        following, _, _ = StageShot(stage,"wide",None,actions=actions,beat=2).at(0.)
        for first, moved, retained in zip(start,end,following):
            self.assertAlmostEqual(moved[2][1,3] - first[2][1,3], 1.)
            self.assertAlmostEqual(moved[2][1,3], retained[2][1,3])

    def test_freewheel_keeps_the_ratchet_moving_after_the_sprocket_stops(self):
        selected = matching_subjects("Explain how a bicycle freewheel coasts.")
        self.assertEqual([template.id for template in selected], ["freewheel-cutaway"])
        for view in ("engagement", "coasting"):
            shot = Shot("freewheel",view,(360,640),offset=2.)
            first, _, _ = shot.at(.2)
            last, _, _ = shot.at(.8)
            matrices = lambda rows: {group: matrix.tolist() for _, _, matrix, group in rows}
            before, after = matrices(first), matrices(last)
            self.assertNotEqual(before["ratchet"], after["ratchet"])
            self.assertEqual(before["sprocket"] == after["sprocket"], view == "coasting")

    def test_toaster_plan_moves_bread_through_a_complete_cycle(self):
        with patch("ai_video._request_storyboard") as request:
            template, _, _, scenes = plan_video("Animate bread going into a toaster and popping up", None)
            request.assert_not_called()
        self.assertEqual(template.id, "pop-up-toaster")
        self.assertEqual([scene["view"] for scene in scenes],
                         ["wide", "loading", "latch", "heating", "browning", "release", "pop-up"])

        def part(view, time, name):
            shot = Shot("toaster", view, (270,480), duration=1)
            return next((material, model) for _, material, model, group in shot.at(time)[0] if group == name)

        self.assertGreater(part("loading", 0, "bread")[1][1,3], part("loading", 1, "bread")[1][1,3])
        for name in ("carriage", "lever", "bread"):
            self.assertGreater(part("latch", 0, name)[1][1,3], part("latch", 1, name)[1][1,3])
            self.assertAlmostEqual(part("latch", 1, name)[1][1,3], part("release", 1, name)[1][1,3])
            self.assertGreater(part("pop-up", 1, name)[1][1,3], part("pop-up", 0, name)[1][1,3])
        self.assertGreater(part("latch", 0, "spring")[1][1,1], part("latch", 1, "spring")[1][1,1])
        self.assertEqual(part("heating", .7, "heater")[0][3], 7.)
        self.assertLess(part("browning", 1, "bread")[0][0], part("heating", .7, "bread")[0][0])
        self.assertNotEqual(part("release", 0, "latch")[1].tolist(), part("release", 1, "latch")[1].tolist())
        self.assertNotEqual(part("release", 1, "heater")[0][3], 7.)

    def test_ollama_reconnects_after_connection_error_but_does_not_retry_timeout(self):
        reply = requests.Response()
        reply.status_code = 200
        board = {**_EXAMPLE, "template": "bicycle-drivetrain"}
        reply._content = json.dumps({"message": {"content": json.dumps(board)}}).encode()
        with patch.dict(os.environ, {"AI_VIDEO_GEMINI_API_KEY": ""}), patch(
            "ai_video.start_local_ollama"
        ) as start, patch("ai_video.requests.post", side_effect=[requests.ConnectionError(), reply]) as post:
            plan_video("Explain bicycle pedals", TEMPLATES["bicycle-drivetrain"])
            start.assert_called_once()
            self.assertEqual(post.call_count, 2)
            post.reset_mock(side_effect=True)
            post.side_effect = requests.ReadTimeout()
            with self.assertRaisesRegex(ExplainerError, "Ollama took too long"):
                plan_video("Explain bicycle pedals", TEMPLATES["bicycle-drivetrain"])
            post.assert_called_once()

    def test_thumbnail_endpoint_returns_a_jpeg_at_the_requested_time(self):
        data = json.dumps({"url": "https://youtu.be/abcdefghijk", "timestamp": 235.5}).encode()
        request = urllib.request.Request(self.url + "/api/thumbnail", data=data,
                                         headers={"Content-Type": "application/json"})
        with patch("server.capture_thumbnail", return_value=b"\xff\xd8test") as capture:
            with urllib.request.urlopen(request) as response:
                self.assertEqual(response.headers["Content-Type"], "image/jpeg")
                self.assertEqual(response.read(), b"\xff\xd8test")
        capture.assert_called_once_with("https://youtu.be/abcdefghijk", 235.5, None)

    def test_export_job_returns_quickly_and_downloads_finished_mp4(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = os.path.join(tmp, 'clip.mp4')
            with open(output, 'wb') as f:
                f.write(b'test-mp4')
            with open(output+'.captions.json','w') as f:
                json.dump({'words': [{'word':'Hello','start':0,'end':1}]}, f)
            manager = RenderJobs(lambda payload: output)
            with patch('server.EXPORT_JOBS', manager):
                payload = {'url':'https://www.youtube.com/watch?v=dNIef2fGLQY', 'start':0,'duration':2,
                           'title':'My_edited_clip'}
                request = urllib.request.Request(self.url+'/api/exports', data=json.dumps(payload).encode(), headers={'Content-Type':'application/json'})
                with urllib.request.urlopen(request) as response:
                    self.assertEqual(response.status, 202)
                    job = json.load(response)
                manager.pending.join()
                with urllib.request.urlopen(self.url+'/api/exports/'+job['id']) as response:
                    self.assertEqual(json.load(response)['state'], 'complete')
                with urllib.request.urlopen(self.url+'/api/exports/'+job['id']+'/download') as response:
                    self.assertEqual(response.read(), b'test-mp4')
                    self.assertEqual(response.headers['Content-Type'], 'video/mp4')
                    self.assertEqual(response.headers['Content-Disposition'], 'attachment; filename="My_edited_clip.mp4"')
                with urllib.request.urlopen(self.url+'/api/exports/'+job['id']+'/captions') as response:
                    self.assertEqual(json.load(response)['words'][0]['word'], 'Hello')

    def test_local_network_urls_and_unbounded_clips_are_rejected(self):
        for payload in ({'url':'http://127.0.0.1/private'}, {'url':'https://example.com/watch?v=dNIef2fGLQY'},
                        {'url':'https://youtu.be/dNIef2fGLQY','duration':10000}):
            with self.assertRaises(ValueError):
                validate_render_payload(payload)

    def test_two_minute_maximum_applies_to_queued_and_direct_downloads(self):
        payload = {'url': 'https://youtu.be/dNIef2fGLQY', 'duration': 120}
        self.assertEqual(validate_render_payload(payload)['duration'], 120)
        with self.assertRaises(ValueError):
            validate_render_payload({**payload, 'duration': 120.01})
        for path in ('/api/exports', '/api/render-clip'):
            request = urllib.request.Request(
                self.url + path, data=json.dumps({**payload, 'duration': 120.01}).encode(),
                headers={'Content-Type': 'application/json'})
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(request)
            self.assertEqual(error.exception.code, 400)
