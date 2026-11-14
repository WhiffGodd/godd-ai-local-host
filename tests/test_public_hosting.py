import json
import os
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from unittest.mock import patch
from server import ThreadedHTTPServer, GoddAIRequestHandler, validate_render_payload
from render_jobs import RenderJobs
from ai_video import FPS, ExplainerError, _EXAMPLE, _fit_runtime, _validate_plan, plan_video, validate_generation
from explainer_templates import TEMPLATES


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
        self.assertEqual(len({template["id"] for template in catalog["templates"]}), 62)

        with tempfile.TemporaryDirectory() as tmp:
            output = os.path.join(tmp, "preview.mp4")
            with open(output, "wb") as stream:
                stream.write(b"example MP4 data")
            manager = RenderJobs(lambda _: (output, {"title": "A test explainer", "description": "#Shorts"}))
            with patch("server.AI_VIDEO_JOBS", manager):
                request = urllib.request.Request(
                    self.url + "/api/ai-videos", data=b'{"template":"blueprint-lab","example":true}',
                    headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(request) as response:
                    self.assertEqual(response.status, 202)
                    job_id = json.load(response)["id"]
                manager.pending.join()
                source = self.url + f"/api/ai-videos/{job_id}"
                with urllib.request.urlopen(source) as response:
                    self.assertEqual(json.load(response)["metadata"]["title"], "A test explainer")
                request = urllib.request.Request(source + "/video?download=1", headers={"Range": "bytes=8-10"})
                with urllib.request.urlopen(request) as response:
                    self.assertEqual(response.status, 206)
                    self.assertEqual(response.headers["Content-Range"], "bytes 8-10/16")
                    self.assertEqual(response.headers["Content-Disposition"], 'attachment; filename="A_test_explainer.mp4"')
                    self.assertEqual(response.read(), b"MP4")

    def test_explainer_hook_precedes_the_complete_story_and_voice_is_validated(self):
        _, _, scenes = _validate_plan(_EXAMPLE)
        self.assertEqual(scenes[0]["heading"], _EXAMPLE["hook"])
        self.assertEqual(scenes[0]["narration"], _EXAMPLE["hook"])
        self.assertTrue(scenes[0]["opening"])
        self.assertEqual([scene["narration"] for scene in scenes[1:]],
                         [scene["narration"] for scene in _EXAMPLE["scenes"]])
        with self.assertRaises(ValueError):
            _validate_plan({**_EXAMPLE, "hook": "Hello"})
        sample = {"template": "blueprint-lab", "example": True}
        self.assertEqual(validate_generation(sample)["voice"], "expressive")
        self.assertEqual(validate_generation({**sample, "voice": "energetic"})["voice"], "energetic")
        with self.assertRaises(ValueError):
            validate_generation({**sample, "voice": "unknown"})

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

    def test_explainer_auto_selects_template_and_keeps_manual_override(self):
        template_id = "marker-room"
        prompt = "Show a person explaining why leaves change color."
        self.assertEqual(validate_generation({"prompt": prompt})["template"], "auto")
        board = {**_EXAMPLE, "title": "Why Leaves Change Color", "template": template_id,
                 "scenes": [{**scene, "diagram": "presenter"} for scene in _EXAMPLE["scenes"]]}
        with patch.dict(os.environ, {"AI_VIDEO_GEMINI_API_KEY": ""}), patch("ai_video.requests.post") as post:
            post.return_value.json.return_value = {"message": {"content": json.dumps(board)}}
            template, _, _, scenes = plan_video(prompt, None)
            self.assertEqual(template.id, template_id)
            self.assertEqual(scenes[0]["diagram"], "presenter")
            self.assertIn(template_id, post.call_args.kwargs["json"]["format"]["properties"]["template"]["enum"])
            template, *_ = plan_video(prompt, TEMPLATES["orbit-theater"])
            self.assertEqual(template.id, "orbit-theater")
            self.assertNotIn("template", post.call_args.kwargs["json"]["format"]["properties"])

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
