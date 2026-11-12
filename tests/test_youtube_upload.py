import json
import os
import tempfile
import threading
import time
import unittest
from http.client import HTTPConnection
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from unittest.mock import Mock, patch

import requests

import server
from api import youtube_upload as youtube
from render_jobs import RenderJobs


def response(code, data=None, headers=None):
    result = Mock(status_code=code, headers=headers or {})
    result.json.return_value = data
    return result


class YouTubeUploadTests(unittest.TestCase):
    def test_short_thumbnail_waits_for_processing_and_targets_uploaded_video(self):
        def processing(state):
            return response(200, {"items": [{"processingDetails": {"processingStatus": state}}]})

        accepted = response(200)
        accepted.ok = True
        with patch.object(youtube.requests, "get", side_effect=[
            processing("processing"), processing("succeeded"),
        ]) as status, patch.object(youtube.requests, "post", return_value=accepted) as upload, patch.object(
            youtube.time, "sleep"
        ):
            self.assertIsNone(youtube.set_video_thumbnail("abcdefghijk", "token", b"jpeg"))
        self.assertEqual(status.call_count, 2)
        self.assertEqual(upload.call_args.kwargs["params"], {"videoId": "abcdefghijk", "uploadType": "media"})
        self.assertEqual(upload.call_args.kwargs["data"], b"jpeg")

    def test_thumbnail_failure_does_not_fail_or_repeat_the_video_upload(self):
        warning = "Channel does not allow custom thumbnails."
        publisher = Mock(return_value={"video_id": "abcdefghijk", "privacy": "private"})
        thumbnailer = Mock(return_value=warning)
        jobs = RenderJobs(lambda payload: "rendered.mp4", publisher=publisher, thumbnailer=thumbnailer)
        job = jobs.submit({"thumbnail_time": 10}, owner="browser")
        jobs.pending.join()
        jobs.thumbnails.join()
        result = jobs.snapshot(job["id"], "browser")
        self.assertEqual(result["state"], "complete")
        self.assertEqual(result["video_id"], "abcdefghijk")
        self.assertFalse(result["thumbnail_applied"])
        self.assertEqual(result["thumbnail_warning"], warning)
        publisher.assert_called_once()
        thumbnailer.assert_called_once()

    def test_resumes_same_session_after_a_lost_response(self):
        metadata = youtube.upload_metadata({"title": "A clip", "made_for_kids": False})
        self.assertEqual(metadata["status"]["privacyStatus"], "private")
        location = "https://www.googleapis.com/upload/youtube/v3/videos?upload_id=test"
        with tempfile.TemporaryDirectory() as directory:
            video = Path(directory, "clip.mp4")
            video.write_bytes(b"abcdefghij")
            with patch.object(youtube, "CHUNK_BYTES", 4), patch.object(
                    youtube.requests, "post", return_value=response(200, headers={"Location": location})
            ) as initiate, patch.object(youtube.requests, "put", side_effect=[
                    requests.Timeout(),
                    response(308, headers={"Range": "bytes=0-3"}),
                    response(308, headers={"Range": "bytes=0-7"}),
                    response(201, {"id": "abcdefghijk", "status": {"privacyStatus": "private"}})
            ]) as send, patch.object(youtube.time, "sleep"):
                result = youtube.upload_video(video, "access-token", metadata)
        initiate.assert_called_once()
        self.assertEqual([call.kwargs["headers"]["Content-Range"] for call in send.call_args_list],
                         ["bytes 0-3/10", "bytes */10", "bytes 4-7/10", "bytes 8-9/10"])
        self.assertEqual(result, {"video_id": "abcdefghijk", "privacy": "private"})

    def test_missing_audience_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "made for kids"):
            youtube.upload_metadata({"title": "A clip"})

    def test_callback_and_upload_are_scoped_to_the_connected_browser(self):
        with server.ThreadedHTTPServer(("127.0.0.1", 0), server.GoddAIRequestHandler) as httpd:
            host, port = httpd.server_address
            origin = f"http://{host}:{port}"
            with patch.dict(os.environ, {"YOUTUBE_OAUTH_CLIENT_ID": "client",
                                         "YOUTUBE_OAUTH_CLIENT_SECRET": "test-secret",
                                         "YOUTUBE_OAUTH_REDIRECT_URI": origin + youtube.CALLBACK_PATH}):
                auth = youtube.YouTubeConnections()
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(thread.join)
            try:
                self._exercise_upload(httpd, origin, auth)
            finally:
                httpd.shutdown()

    def _exercise_upload(self, httpd, origin, auth):
        host, port = httpd.server_address

        def request(method, path, body=None, cookie=None, request_origin=origin):
            headers = {"Origin": request_origin, "Content-Type": "application/json"}
            if cookie:
                headers["Cookie"] = cookie
            conn = HTTPConnection(host, port, timeout=3)
            try:
                conn.request(method, path, json.dumps(body) if body is not None else None, headers)
                resp = conn.getresponse()
                content = resp.read()
                content_type = resp.getheader("Content-Type", "")
                data = json.loads(content) if content_type.startswith("application/json") else content
                return resp.status, data, resp.getheader("Set-Cookie") or resp.getheader("Location")
            finally:
                conn.close()

        started = threading.Event()
        release = threading.Event()

        def render(_):
            started.set()
            release.wait(3)
            return "rendered.mp4"

        with patch.object(server, "YOUTUBE", auth), patch.object(
            youtube.requests, "post", return_value=response(200, {"access_token": "token", "refresh_token": "refresh"})
        ), patch.object(youtube.requests, "get", return_value=response(200, {
            "items": [{"id": "test-channel", "snippet": {"title": "My channel"}}]
        })), patch.object(server, "upload_video", return_value={"video_id": "abcdefghijk", "privacy": "private"}) as publish:
            jobs = RenderJobs(render, publisher=server.publish_to_youtube)
            with patch.object(server, "EXPORT_JOBS", jobs):
                self.assertEqual(request("POST", "/api/youtube/connect", {}, request_origin="https://elsewhere.test")[0], 403)
                status, link, raw_cookie = request("POST", "/api/youtube/connect", {})
                self.assertEqual(status, 200)
                self.assertIn("HttpOnly", raw_cookie)
                cookie = raw_cookie.split(";", 1)[0]
                state = parse_qs(urlsplit(link["url"]).query)["state"][0]
                callback = youtube.CALLBACK_PATH + f"?code=fake&state={state}"
                self.assertEqual(request("GET", callback)[0], 400)
                self.assertEqual(request("GET", callback, cookie=cookie), (303, b"", "/?youtube=connected"))
                self.assertEqual(request("GET", callback, cookie=cookie)[0], 400)
                self.assertEqual(request("GET", "/api/youtube/status")[1]["channel"], None)
                self.assertEqual(request("GET", "/api/youtube/status", cookie=cookie)[1]["channel"]["id"], "test-channel")
                payload = {"request_id": "unique-request-id", "channel_id": "test-channel",
                           "url": "https://youtu.be/abcdefghijk", "duration": 70,
                           "title": "Clip", "made_for_kids": False}
                self.assertEqual(request("POST", "/api/youtube/uploads", payload)[0], 401)
                self.assertEqual(request("POST", "/api/youtube/uploads", {**payload, "channel_id": "stale"}, cookie)[0], 409)
                status, job, _ = request("POST", "/api/youtube/uploads", payload, cookie)
                try:
                    self.assertEqual(status, 202)
                    self.assertTrue(started.wait(2))
                    job_path = "/api/youtube/uploads/" + job["id"]
                    self.assertEqual(request("GET", job_path)[0], 404)
                    self.assertEqual(request("POST", "/api/youtube/uploads", payload, cookie)[1]["id"], job["id"])
                    self.assertIsNone(jobs.snapshot(job["id"]))
                finally:
                    release.set()
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline and request("GET", job_path, cookie=cookie)[1]["state"] != "complete":
                    time.sleep(.01)
                result = request("GET", job_path, cookie=cookie)[1]
                self.assertEqual(result["video_id"], "abcdefghijk")
                self.assertEqual(result["privacy"], "private")
                publish.assert_called_once()
                self.assertEqual(request("POST", "/api/youtube/disconnect", {}, cookie)[0], 200)
                self.assertEqual(request("GET", "/api/youtube/status", cookie=cookie)[1]["channel"], None)
