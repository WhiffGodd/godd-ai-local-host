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
        for path in ('/', '/app.js', '/style.css', '/youtube-studio.js', '/privacy.html'):
            with urllib.request.urlopen(self.url + path) as response:
                self.assertEqual(response.status, 200)
        for path in ('/.git/config', '/server.py', '/.env', '/../server.py', '/public/speech_accuracy_check.json'):
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(self.url + path)
            self.assertEqual(error.exception.code, 404)

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
