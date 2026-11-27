# SPDX-License-Identifier: MIT
"""Optional persistent Blender EEVEE renderer behind the studio frame interface."""
from collections import deque
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import tempfile
import threading
import time

import numpy as np
from PIL import Image

from cinematic_render import RendererUnavailable, _part_badge
from cinematic_geometry import mesh
from mechanism_attachments import validate_bindings
from solid_geometry import physical_dimensions


ROOT=Path(__file__).resolve().parent


def blender_executable():
    configured=os.environ.get('BLENDER_PATH')
    if configured:
        path=Path(configured)
        return str(path) if path.is_file() else None
    found=shutil.which('blender')
    if found:return found
    paths=list((ROOT/'.tools'/'blender').glob('*/blender.exe'))
    for base in (Path(os.environ.get('PROGRAMFILES','C:/Program Files'))/'Blender Foundation',):
        paths.extend(base.glob('Blender */blender.exe'))
    return str(max(paths,key=lambda p:tuple(map(int,re.findall(r'\d+',p.parent.name))))) if paths else None


def blender_settings():
    return dict(blender_available=bool(blender_executable()))


def procedural_description(component,index,world):
    if component.shape!='solid' or index>=len(component.geometry):return None
    piece=component.geometry[index]
    left,top=np.min(component.points,axis=0);right,bottom=np.max(component.points,axis=0)
    unit=np.linalg.norm(world((1,0))-world((0,0)));w,h=(right-left)*unit,(bottom-top)*unit;depth=min(w,h)*.75
    cx,cy,cz=piece.center
    return dict(primitive=piece.primitive,profile=[list(p) for p in piece.profile],axis=piece.axis,
        center=world((left+cx*(right-left),top+cy*(bottom-top)),(cz-.5)*depth).tolist(),
        dimensions=physical_dimensions(piece.primitive,piece.axis,np.array((w,h,depth))*piece.size).tolist(),
        cutaway=bool(re.search(r'\b(housing|casing|enclosure|case|shell)\b',component.part.label,re.I)))


class BlenderRenderer:
    def __init__(self,size=(720,1280),model=None,bindings=None,samples=32,timeout=150):
        if len(size)!=2 or any(type(v) is not int or not 64<=v<=2160 for v in size):raise ValueError('Unsupported preview resolution')
        self.executable=blender_executable()
        if not self.executable:raise RendererUnavailable('Blender is unavailable. Install Blender or choose the standard renderer.')
        self.size=tuple(size);self.samples=max(8,min(64,int(samples)));self.timeout=timeout
        self.meshes={};self.descriptions={};self.sent=set();self.process=None;self.events=queue.Queue();self.logs=deque(maxlen=100)
        self.workspace=tempfile.TemporaryDirectory(prefix='godd_blender_');self.root=Path(self.workspace.name)
        self.bindings={**(model.attachments if model else {}),**(bindings or {})};self.closed=False;self.timings=[]
        if model:
            groups={p.part.label for p in model.parts};validate_bindings(self.bindings,groups)
            counts={}
            for component,_,name,_,_,_ in model.compiled:
                index=counts.get(component.part.label,0);counts[component.part.label]=index+1
                desc=procedural_description(component,index,model.world)
                if desc:self.descriptions[name]=desc

    def __enter__(self):return self
    def __exit__(self,*_):self.close()

    def register_mesh(self,name,vertices):
        if name in self.meshes:return
        vertices=np.asarray(vertices,dtype=np.float32)
        if vertices.ndim!=2 or vertices.shape[1]!=6 or len(vertices)%3 or not len(vertices) or len(vertices)>2_000_000 or not np.isfinite(vertices).all():raise ValueError('Invalid Blender mesh')
        filename=hashlib.sha256(name.encode()).hexdigest()[:24]+'.npz'
        if name not in self.descriptions:np.savez_compressed(self.root/filename,vertices=vertices)
        self.meshes[name]=dict(procedural=self.descriptions[name]) if name in self.descriptions else dict(file=filename)

    def _read(self):
        for line in self.process.stdout:
            if line.startswith('GODD_BLENDER '):
                try:self.events.put(json.loads(line[len('GODD_BLENDER '):]))
                except ValueError:self.logs.append(line.strip())
            else:self.logs.append(line.strip())
        self.events.put(dict(state='exit'))

    def _event(self):
        try:event=self.events.get(timeout=self.timeout)
        except queue.Empty:
            self.close();raise RendererUnavailable('Blender did not finish the preview within its time limit. Try a simpler scene or the standard renderer.') from None
        if event.get('state') in ('error','exit'):
            detail=event.get('message') or '\n'.join(self.logs)[-1500:]
            raise RendererUnavailable('Blender could not render the scene: '+detail)
        return event

    def _start(self):
        if self.process:return
        command=[self.executable,'--background','--factory-startup','--python-exit-code','1','--python',str(ROOT/'blender_worker.py'),'--',
                 '--root',str(self.root),'--width',str(self.size[0]),'--height',str(self.size[1]),'--samples',str(self.samples)]
        flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
        self.process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
            text=True,encoding='utf8',errors='replace',bufsize=1,creationflags=flags)
        threading.Thread(target=self._read,daemon=True).start()
        if self._event().get('state')!='ready':raise RendererUnavailable('Blender did not initialize correctly')

    def frame(self,shot,elapsed,part=None,subtitle=None):
        started=time.monotonic();objects,eye,focus=shot.at(elapsed,part)
        previous=getattr(shot,'camera_from',None)
        if previous is not None and elapsed<.8:
            amount=min(1,max(0,elapsed/.8));amount=amount**3*(10+amount*(-15+6*amount))
            eye=np.array(previous[0])+(np.array(eye)-previous[0])*amount
            focus=np.array(previous[1])+(np.array(focus)-previous[1])*amount
        self.last_camera=(np.array(eye).copy(),np.array(focus).copy())
        if hasattr(shot,'camera'):shot.camera=self.last_camera
        counts={};packets=[]
        for name,material,matrix,group in objects:
            if name not in self.meshes:self.register_mesh(name,mesh(name))
            key=(name,group);index=counts.get(key,0);counts[key]=index+1
            matrix=np.asarray(matrix,dtype=float)
            if matrix.shape!=(4,4) or not np.isfinite(matrix).all():raise ValueError('Invalid Blender pose')
            packets.append(dict(id=hashlib.sha256(f'{name}|{group}|{index}'.encode()).hexdigest()[:24],asset=name,
                                group=group or 'Scene',material=list(material),matrix=matrix.tolist()))
        present={p['group'] for p in packets}
        bindings={child:parent for child,parent in self.bindings.items() if child in present and parent in present}
        validate_bindings(bindings,present)
        self._start();assets={k:v for k,v in self.meshes.items() if k not in self.sent}
        command=dict(command='frame',assets=assets,objects=packets,eye=list(eye),focus=list(focus),floor=getattr(shot,'floor',-1.25),
                     space=shot.subject=='moon',bindings=bindings)
        self.process.stdin.write(json.dumps(command,separators=(',',':'),allow_nan=False)+'\n');self.process.stdin.flush()
        event=self._event()
        if event.get('state')!='frame':raise RendererUnavailable('Blender returned an unexpected frame response')
        self.sent.update(assets)
        with Image.open(self.root/'frame.png') as picture:frame=picture.convert('RGB').copy()
        if part:
            layer,xy=_part_badge(part.label,self.size);frame.paste(layer,xy,layer)
        if hasattr(shot,'overlay'):shot.overlay(frame,elapsed)
        caption=subtitle or getattr(shot,'caption',None)
        if caption:
            layer,xy=caption;frame.paste(layer,xy,layer)
        self.timings.append(time.monotonic()-started)
        return frame

    def close(self):
        if self.closed:return
        self.closed=True
        if self.process and self.process.poll() is None:
            try:
                self.process.stdin.write('{"command":"quit"}\n');self.process.stdin.flush();self.process.wait(timeout=5)
            except (OSError,ValueError,subprocess.TimeoutExpired):
                self.process.kill();self.process.wait(timeout=5)
        if self.process:
            for stream in (self.process.stdin,self.process.stdout):
                if stream:
                    try:stream.close()
                    except OSError:pass
        self.workspace.cleanup()
