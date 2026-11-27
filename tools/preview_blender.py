# SPDX-License-Identifier: MIT
"""Compare identical five-second mechanism plans on both renderers."""
import argparse
import bisect
import json
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cinematic_render import CinematicRenderer
from mechanism_animation import read_mechanism
from mechanism_3d import Mechanism3D,Mechanism3DShot
from blender_renderer import BlenderRenderer
from sliding_latch import latch_mechanism
from biology_explainers import biology_mechanism
from biology_shots import BIOLOGY_SHOTS
from video_engine import FFMPEG_PATH


def fixture(name):
    if name=='motor':
        parts=[dict(name='Motor',shape='motor',color='steel',pivot=[50,50],points=[[18,18],[82,82]])]
        actions=[dict(beat=1,part='Motor',effect='spin',amount=[.5,0],start=.05,end=.25)]
        return read_mechanism(dict(parts=parts,actions=actions),2),[.1,5.],Mechanism3DShot,{}
    if name=='profiles':
        shaft_profile=[[0,0],[.7,0],[.7,.1],[1,.1],[1,.2],[.45,.2],[.45,.8],[.8,.8],[.8,1],[0,1]]
        collar_profile=[[.75,0],[1,0],[1,1],[.75,1]]
        parts=[dict(name='Stepped spindle',shape='solid',color='steel',pivot=[50,50],points=[[35,10],[65,90]],rotation_axis='y',
                    geometry=[dict(primitive='lathe',axis='y',center=[.5,.5,.5],size=[1,.95,1],color='steel',profile=shaft_profile)]),
               dict(name='Collar',shape='solid',color='gold',pivot=[50,50],points=[[30,40],[70,60]],parent='Stepped spindle',
                    geometry=[dict(primitive='lathe',axis='y',center=[.5,.5,.5],size=[.65,.8,1],color='gold',profile=collar_profile)]),
               dict(name='Bracket',shape='solid',color='blue',pivot=[50,50],points=[[55,45],[88,65]],parent='Stepped spindle',
                    geometry=[dict(primitive='extrude',axis='z',center=[.5,.5,.5],size=[1,1,.35],color='blue',
                                   profile=[[0,0],[1,0],[1,.25],[.25,.25],[.25,1],[0,1]] )])]
        actions=[dict(beat=1,part='Stepped spindle',effect='spin',amount=[.3,0],start=.05,end=.25)]
        return read_mechanism(dict(parts=parts,actions=actions),2),[.1,5],Mechanism3DShot,{}
    if name=='latch':return latch_mechanism(6),[.1,1,1,1,1,1],Mechanism3DShot,{'Pull handle':'Sliding bolt'}
    if name=='alveolus':return biology_mechanism('alveolar-gas-exchange',6),[.1,1,1,1,1,1],BIOLOGY_SHOTS['alveolar-gas-exchange'],{}
    raise ValueError('Unknown benchmark')


def preview(name,engine,output,size=(360,640),seconds=5,fps=30,samples=16):
    mechanism,durations,shot_type,bindings=fixture(name)
    model=Mechanism3D(mechanism);model.set_timeline(durations)
    renderer=(BlenderRenderer(size,model,bindings,samples=samples) if engine=='blender' else CinematicRenderer(size))
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    command=[FFMPEG_PATH,'-y','-v','error','-f','rawvideo','-pixel_format','rgb24','-video_size',f'{size[0]}x{size[1]}',
             '-framerate',str(fps),'-i','-','-an','-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-movflags','+faststart',str(output)]
    bounds=[0]
    for duration in durations:bounds.append(bounds[-1]+duration)
    started=time.monotonic();timings=[]
    with renderer,subprocess.Popen(command,stdin=subprocess.PIPE,stderr=subprocess.PIPE) as encoder:
        try:
            model.upload(renderer)
            for i in range(round(seconds*fps)):
                elapsed=.1+i/fps*5/seconds
                beat=min(len(durations)-1,bisect.bisect_right(bounds,elapsed)-1)
                local=elapsed-bounds[beat]
                shot=shot_type(model,size,beat,'wide',durations[beat],bounds[beat])
                begin=time.monotonic();image=renderer.frame(shot,local);timings.append(time.monotonic()-begin)
                if i in (0,round(seconds*fps)//2,round(seconds*fps)-1):image.save(output.with_name(output.stem+f'-{i:03}.png'))
                encoder.stdin.write(image.tobytes())
                if i%30==0:print(name,engine,i,'/',round(seconds*fps),round(timings[-1],3),'seconds/frame',flush=True)
            encoder.stdin.close();error=encoder.stderr.read().decode();code=encoder.wait(timeout=30)
            if code:raise RuntimeError(error)
        finally:
            if encoder.poll() is None:encoder.kill();encoder.wait()
    record=dict(case=name,renderer=engine,frames=len(timings),duration=seconds,resolution=size,elapsed=time.monotonic()-started,
                first_frame=timings[0],average_after_first=sum(timings[1:])/max(1,len(timings)-1),file=str(output.resolve()))
    output.with_suffix('.json').write_text(json.dumps(record,indent=2));print(json.dumps(record),flush=True)
    return record


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--case',choices=['motor','latch','alveolus','profiles','all'],default='all')
    parser.add_argument('--renderer',choices=['blender','standard','both'],default='both');parser.add_argument('--seconds',type=float,default=5)
    parser.add_argument('--fps',type=int,default=30);parser.add_argument('--samples',type=int,default=16)
    parser.add_argument('--size',default='360x640');parser.add_argument('--output',type=Path,default=Path('.tools/blender-previews'))
    args=parser.parse_args();size=tuple(map(int,args.size.split('x')))
    if len(size)!=2 or not .1<=args.seconds<=10 or not 1<=args.fps<=30:parser.error('Invalid preview dimensions or timing')
    for name in (['motor','latch','alveolus'] if args.case=='all' else [args.case]):
        for engine in (['standard','blender'] if args.renderer=='both' else [args.renderer]):
            preview(name,engine,args.output/f'{name}-{engine}.mp4',size,args.seconds,args.fps,args.samples)


if __name__=='__main__':main()
