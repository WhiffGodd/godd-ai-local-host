"""Bounded background exports so hosting proxies never wait for an encode."""
import os
import queue
import secrets
import threading
import time
from collections import OrderedDict
from api.youtube_access import download_error_response
from api.youtube_upload import YouTubeUploadError
from generated_video_store import GeneratedVideoStore


class RenderJobs:
    def __init__(self, renderer, max_pending=4, lifetime=1800, publisher=None, thumbnailer=None,
                 report_progress=False, storage_dir=None, on_published=None):
        self.renderer = renderer
        self.publisher = publisher
        self.thumbnailer = thumbnailer
        self.report_progress = report_progress
        self.on_published = on_published
        self.pending = queue.Queue(maxsize=max_pending)
        self.store = GeneratedVideoStore(storage_dir,lifetime) if storage_dir else None
        if self.store and (publisher or thumbnailer):raise ValueError("Generated-video storage is only for local render jobs")
        self.jobs = OrderedDict(self.store.restore() if self.store else [])
        self.lock = threading.Lock()
        self.lifetime = lifetime
        threading.Thread(target=self._work, daemon=True).start()
        if thumbnailer:
            self.thumbnails = queue.Queue()
            threading.Thread(target=self._finish_thumbnails, daemon=True).start()

    def _prune(self):
        now = time.monotonic()
        if self.store:self.store.prune()
        for token, job in list(self.jobs.items()):
            age=time.time()-job.get('_saved_at',time.time()) if self.store else now-job['updated']
            if job['state'] in ('complete', 'failed', 'uploaded') and age > self.lifetime:
                path = job.get('path')
                if path:
                    for suffix in ('', '.captions.json', '.srt'):
                        try:
                            os.remove(path+suffix)
                        except OSError:
                            pass
                if self.store:self.store.delete(token)
                del self.jobs[token]

    def _persist(self,job):
        if self.store:self.store.save(job)

    def _lookup(self,token):
        return self.jobs.get(token) or (self.store.load(token) if self.store else None)

    def submit(self, payload, owner=None, request_id=None):
        token = secrets.token_urlsafe(24)
        job = {'id': token, 'state': 'queued', 'updated': time.monotonic(), 'payload': payload,
               'owner': owner, 'request_id': request_id}
        if self.store:
            if owner is not None:raise ValueError('Generated video storage cannot store account jobs')
            job['_generation_payload']=dict(payload)
        if not owner and payload.get('filename'):
            job['filename'] = payload['filename']
        with self.lock:
            self._prune()
            if owner and request_id:
                for existing in self.jobs.values():
                    if existing['owner'] == owner and existing['request_id'] == request_id:
                        return self._status(existing)
            if self.store:
                # Archived finished jobs stay on disk and remain addressable.
                for old_token,old in list(self.jobs.items()):
                    if len(self.jobs)<24:break
                    if old['state'] in ('complete','failed','uploaded'):del self.jobs[old_token]
            if len(self.jobs) >= 24:
                raise queue.Full
            self.jobs[token] = job
            try:
                self._persist(job)
                self.pending.put_nowait(token)
            except (queue.Full,OSError,ValueError):
                del self.jobs[token]
                if self.store:self.store.delete(token)
                raise
        return self.snapshot(token, owner)

    @staticmethod
    def _status(job):
        return {k: job[k] for k in ('id', 'state', 'error', 'code', 'video_id', 'privacy', 'filename', 'metadata',
                                   'thumbnail_applied', 'thumbnail_warning', 'progress', 'local_copy_deleted', 'cleanup_warning') if k in job}

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
            job = self._lookup(token)
            if not job or job['owner'] != owner:
                return None
            return self._status(job)

    def completed_path(self, token):
        with self.lock:
            self._prune()
            job = self._lookup(token)
            path=job.get('path') if job and job['owner'] is None and job['state']=='complete' else None
            return path if path and os.path.isfile(path) else None

    def mark_uploaded(self,token,result):
        with self.lock:
            job=self._lookup(token)
            if not job:return
            path=job.get('path')
            if path:
                for suffix in ('','.captions.json','.srt'):
                    try:os.remove(path+suffix)
                    except FileNotFoundError:pass
            job.pop('path',None)
            job.update(state='uploaded',video_id=result['video_id'],updated=time.monotonic())
            if result.get('privacy'):job['privacy']=result['privacy']
            self._persist(job)
            self.jobs[token]=job

    def _after_publish(self,owner,payload,path,result):
        if not self.on_published or not result.get('video_id'):return {}
        try:
            self.on_published(owner,payload,path,result)
            return dict(local_copy_deleted=True)
        except Exception as error:
            print('Uploaded video cleanup failed:',error,flush=True)
            return dict(cleanup_warning='The video is uploaded, but its local copy could not be removed. Close the preview and retry cleanup.')

    def _work(self):
        while True:
            token = self.pending.get()
            try:
                with self.lock:
                    job = self.jobs[token]
                    job['state'] = 'rendering'
                    payload = job.pop('payload')
                    self._persist(job)
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
                cleanup=self._after_publish(job['owner'],payload,path,result) if not needs_thumbnail else {}
                with self.lock:
                    job.pop('progress', None)
                    job.update(state='thumbnail_processing' if needs_thumbnail else 'complete',
                               updated=time.monotonic(), **result, **cleanup)
                    self._persist(job)
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
                    try:self._persist(self.jobs[token])
                    except (OSError,ValueError) as storage_error:print('Could not save generated video status:',storage_error,flush=True)
            finally:
                self.pending.task_done()

    def _finish_thumbnails(self):
        while True:
            token, owner, payload, path, video_id = self.thumbnails.get()
            try:
                warning = self.thumbnailer(owner, payload, path, video_id)
            except Exception:
                warning = "Could not apply the thumbnail. The uploaded video is available in YouTube Studio."
            with self.lock:result=self._status(self.jobs[token])
            cleanup=self._after_publish(owner,payload,path,result)
            with self.lock:
                self.jobs[token].update(state='complete', updated=time.monotonic(),
                                        thumbnail_applied=not warning, thumbnail_warning=warning, **cleanup)
            self.thumbnails.task_done()
