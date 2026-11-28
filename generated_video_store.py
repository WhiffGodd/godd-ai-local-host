# SPDX-License-Identifier: MIT
"""Private local storage for generated videos and restart-safe job records."""
import json
import os
from pathlib import Path
import re
import shutil
import time


class GeneratedVideoStore:
    def __init__(self, root, lifetime):
        self.root=Path(root).resolve();self.root.mkdir(parents=True,exist_ok=True)
        self.lifetime=lifetime;self.last_prune=None

    def path(self, token, suffix):
        if not isinstance(token,str) or not re.fullmatch(r'[A-Za-z0-9_-]{20,80}',token):return None
        path=self.root/(token+suffix)
        return path if path.resolve().parent==self.root else None

    def save(self, job):
        if job['owner'] is not None:raise ValueError('Private account upload jobs cannot use generated-video storage')
        token=job['id'];record=self.path(token,'.json');owned_temporary=None
        if record is None:raise ValueError('Invalid generated video identifier')
        if job['state']=='complete':
            source=Path(job['path']);destination=self.path(token,'.mp4')
            if destination is None:raise ValueError('Invalid generated video path')
            if source.resolve()!=destination:
                temporary=self.path(token,'.mp4.part')
                try:
                    shutil.copyfile(source,temporary);os.replace(temporary,destination)
                finally:
                    temporary.unlink(missing_ok=True)
                job['path']=str(destination)
                # AI renderer outputs are owned temporary files; unrelated source
                # files (including caller fixtures) remain untouched.
                if source.name.startswith('godd_ai_video_'):owned_temporary=source
            if not destination.is_file():raise FileNotFoundError('The generated video could not be saved')
        public=('id','state','error','code','filename','metadata','progress','video_id','privacy')
        data={k:job[k] for k in public if k in job}
        data['saved_at']=time.time();data['payload']=job.get('_generation_payload',{})
        temporary=self.path(token,'.json.part')
        try:
            with temporary.open('w',encoding='utf8') as output:
                json.dump(data,output,ensure_ascii=True,allow_nan=False)
                output.flush();os.fsync(output.fileno())
            os.replace(temporary,record)
            job['_saved_at']=data['saved_at']
        finally:temporary.unlink(missing_ok=True)
        if owned_temporary is not None:
            try:owned_temporary.unlink(missing_ok=True)
            except OSError:pass

    def delete(self, token):
        for suffix in ('.json','.json.part','.mp4','.mp4.part'):
            path=self.path(token,suffix)
            if path is not None:path.unlink(missing_ok=True)

    def load(self, token, recover=False):
        record=self.path(token,'.json')
        if record is None or not record.is_file():return None
        try:
            data=json.loads(record.read_text(encoding='utf8'))
            saved=float(data['saved_at']);age=max(0,time.time()-saved)
            if data['id']!=token or data['state'] not in ('queued','rendering','complete','failed','uploaded'):return None
            if age>self.lifetime:
                self.delete(token);return None
            job={k:data[k] for k in ('id','state','error','code','filename','metadata','progress','video_id','privacy') if k in data}
            job.update(owner=None,request_id=None,updated=time.monotonic()-age,_saved_at=saved,_generation_payload=data.get('payload',{}))
            if job['state']=='complete':
                path=self.path(token,'.mp4')
                if path is not None and path.is_file():job['path']=str(path)
                else:
                    job.update(state='failed',code='VIDEO_FILE_MISSING',error='The saved video file is unavailable. Your prompt is kept; generate the video again.')
            elif recover and job['state'] in ('queued','rendering'):
                job.pop('progress',None)
                job.update(state='failed',code='GENERATION_INTERRUPTED',error='The studio restarted while this video was being prepared. Your prompt is kept; generate it again.')
            if job['state']=='failed' and job['state']!=data['state']:
                job['updated']=time.monotonic();self.save(job)
            return job
        except (OSError,ValueError,KeyError,TypeError):return None

    def restore(self):
        jobs=[]
        for record in self.root.glob('*.json'):
            job=self.load(record.stem,recover=True)
            if job:jobs.append((job['id'],job))
        return sorted(jobs,key=lambda item:item[1]['updated'])[-24:]

    def prune(self):
        now=time.monotonic()
        if self.last_prune is not None and now-self.last_prune<60:return
        self.last_prune=now
        for record in self.root.glob('*.json'):self.load(record.stem)
