"""Bounded background exports so hosting proxies never wait for an encode."""
import os
import queue
import secrets
import threading
import time
from collections import OrderedDict
from api.youtube_access import download_error_response
from api.youtube_upload import YouTubeUploadError


class RenderJobs:
    def __init__(self, renderer, max_pending=4, lifetime=1800, publisher=None):
        self.renderer = renderer
        self.publisher = publisher
        self.pending = queue.Queue(maxsize=max_pending)
        self.jobs = OrderedDict()
        self.lock = threading.Lock()
        self.lifetime = lifetime
        threading.Thread(target=self._work, daemon=True).start()

    def _prune(self):
        now = time.monotonic()
        for token, job in list(self.jobs.items()):
            if job['state'] in ('complete', 'failed') and now-job['updated'] > self.lifetime:
                path = job.get('path')
                if path:
                    for suffix in ('', '.captions.json', '.srt'):
                        try:
                            os.remove(path+suffix)
                        except OSError:
                            pass
                del self.jobs[token]

    def submit(self, payload, owner=None, request_id=None):
        token = secrets.token_urlsafe(24)
        job = {'id': token, 'state': 'queued', 'updated': time.monotonic(), 'payload': payload,
               'owner': owner, 'request_id': request_id}
        if not owner and payload.get('filename'):
            job['filename'] = payload['filename']
        with self.lock:
            self._prune()
            if owner and request_id:
                for existing in self.jobs.values():
                    if existing['owner'] == owner and existing['request_id'] == request_id:
                        return self._status(existing)
            if len(self.jobs) >= 24:
                raise queue.Full
            self.jobs[token] = job
            try:
                self.pending.put_nowait(token)
            except queue.Full:
                del self.jobs[token]
                raise
        return self.snapshot(token, owner)

    @staticmethod
    def _status(job):
        return {k: job[k] for k in ('id', 'state', 'error', 'code', 'video_id', 'privacy', 'filename') if k in job}

    def snapshot(self, token, owner=None):
        with self.lock:
            self._prune()
            job = self.jobs.get(token)
            if not job or job['owner'] != owner:
                return None
            return self._status(job)

    def completed_path(self, token):
        with self.lock:
            self._prune()
            job = self.jobs.get(token)
            return job.get('path') if job and job['owner'] is None and job['state'] == 'complete' else None

    def _work(self):
        while True:
            token = self.pending.get()
            try:
                with self.lock:
                    job = self.jobs[token]
                    job['state'] = 'rendering'
                    payload = job.pop('payload')
                path = self.renderer(payload)
                with self.lock:
                    job['path'] = path
                    if job['owner']:
                        job['state'] = 'uploading'
                result = self.publisher(job['owner'], payload, path) if job['owner'] else {}
                with self.lock:
                    job.update(state='complete', updated=time.monotonic(), **result)
            except YouTubeUploadError as error:
                with self.lock:
                    self.jobs[token].update(state='failed', code='YOUTUBE_UPLOAD_FAILED', error=str(error),
                                            updated=time.monotonic())
            except Exception as error:
                _, code, message = download_error_response(error)
                with self.lock:
                    self.jobs[token].update(state='failed', code=code, error=message, updated=time.monotonic())
            finally:
                self.pending.task_done()
