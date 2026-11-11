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
        for path in ('/', '/app.js', '/style.css', '/youtube-studio.js'):
            with urllib.request.urlopen(self.url + path) as response:
                self.assertEqual(response.status, 200)
        for path in ('/.git/config', '/server.py', '/.env', '/../server.py', '/public/speech_accuracy_check.json'):
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(self.url + path)
            self.assertEqual(error.exception.code, 404)

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
