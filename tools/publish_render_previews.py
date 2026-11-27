# SPDX-License-Identifier: MIT
"""Publish the local comparison renders as small, explicitly allowed web assets."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from video_engine import FFMPEG_PATH


def publish(source):
    root=Path(__file__).resolve().parents[1];target=root/'public'/'cinematic';target.mkdir(exist_ok=True)
    titles={'motor':'Electric motor','latch':'Spring-loaded latch','alveolus':'Alveolar gas exchange','profiles':'Profile-built rotating assembly'}
    manifest=dict(resolution=[360,640],fps=30,duration=5,cases=[])
    for case,title in titles.items():
        item=dict(id=case,title=title)
        for engine in ('standard','blender'):
            video=source/f'{case}-{engine}.mp4';stats=json.loads(video.with_suffix('.json').read_text(encoding='utf8'))
            if stats['duration']!=5 or stats['frames']!=150 or stats['resolution']!=[360,640]:raise ValueError('Comparison videos must use matching five-second 360x640 plans at 30 fps')
            destination=target/f'preview-{case}-{engine}.webm'
            command=[FFMPEG_PATH,'-y','-v','error','-i',str(video),'-an','-c:v','libvpx-vp9','-crf','28','-b:v','0','-deadline','good','-cpu-used','3',str(destination)]
            subprocess.run(command,check=True)
            poster=video.with_name(video.stem+'-075.png')
            with Image.open(poster) as image:image.save(destination.with_suffix('.webp'),format='WEBP',quality=90)
            item[engine]=dict(seconds=round(stats['elapsed'],1),video='/cinematic/'+destination.name,poster='/cinematic/'+destination.with_suffix('.webp').name)
        manifest['cases'].append(item)
    (root/'public'/'render-comparison.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    print('Published four renderer comparisons',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,default=Path('.tools/blender-final'));args=parser.parse_args();publish(args.source)
