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
    def __init__(self, renderer, max_pending=4, lifetime=1800, publisher=None, thumbnailer=None,
                 report_progress=False):
        self.renderer = renderer
        self.publisher = publisher
        self.thumbnailer = thumbnailer
        self.report_progress = report_progress
        self.pending = queue.Queue(maxsize=max_pending)
        self.jobs = OrderedDict()
        self.lock = threading.Lock()
        self.lifetime = lifetime
        threading.Thread(target=self._work, daemon=True).start()
        if thumbnailer:
            self.thumbnails = queue.Queue()
            threading.Thread(target=self._finish_thumbnails, daemon=True).start()

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
        return {k: job[k] for k in ('id', 'state', 'error', 'code', 'video_id', 'privacy', 'filename', 'metadata',
                                   'thumbnail_applied', 'thumbnail_warning', 'progress') if k in job}

    def _render(self, job, payload):
        if not self.report_progress:
            return self.renderer(payload)

        def update(stage, percent):
            with self.lock:
                job["progress"] = {"stage": stage, "percent": percent}

        return self.renderer(payload, report_progress=update)

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
                rendered = self._render(job, payload)
                path, metadata = rendered if isinstance(rendered, tuple) else (rendered, None)
                with self.lock:
                    job['path'] = path
                    if metadata:
                        job['metadata'] = metadata
                    if job['owner']:
                        job['state'] = 'uploading'
                result = self.publisher(job['owner'], payload, path) if job['owner'] else {}
                needs_thumbnail = self.thumbnailer and result.get('video_id') and payload.get('thumbnail_time') is not None
                with self.lock:
                    job.pop('progress', None)
                    job.update(state='thumbnail_processing' if needs_thumbnail else 'complete',
                               updated=time.monotonic(), **result)
                if needs_thumbnail:
                    self.thumbnails.put_nowait((token, job['owner'], payload, path, result['video_id']))
            except YouTubeUploadError as error:
                with self.lock:
                    self.jobs[token].update(state='failed', code='YOUTUBE_UPLOAD_FAILED', error=str(error),
                                            updated=time.monotonic())
            except Exception as error:
                _, code, message = download_error_response(error)
                with self.lock:
                    self.jobs[token].pop('progress', None)
                    self.jobs[token].update(state='failed', code=code, error=message, updated=time.monotonic())
            finally:
                self.pending.task_done()

    def _finish_thumbnails(self):
        while True:
            token, owner, payload, path, video_id = self.thumbnails.get()
            try:
                warning = self.thumbnailer(owner, payload, path, video_id)
            except Exception:
                warning = "Could not apply the thumbnail. The uploaded video is available in YouTube Studio."
            with self.lock:
                self.jobs[token].update(state='complete', updated=time.monotonic(),
                                        thumbnail_applied=not warning, thumbnail_warning=warning)
            self.thumbnails.task_done()
