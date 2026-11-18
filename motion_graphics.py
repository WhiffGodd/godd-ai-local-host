# SPDX-License-Identifier: MIT
"""Layer realistic cutout assets into reusable motion explainer scenes."""

from dataclasses import dataclass
from functools import lru_cache
from hashlib import md5
from math import cos, pi, sin
from pathlib import Path
import re
import os
import tempfile
from urllib.request import urlopen

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from explainer_visuals import VisualUnavailable


POSITIONS = {"center":(.5,.55), "left":(.30,.55), "right":(.70,.55),
             "upper":(.5,.40), "lower":(.5,.68)}
SIZES = {"small":.35, "medium":.58, "large":.85}
ACTIONS = ("hold", "slide-left", "slide-right", "lower", "lift", "rotate", "orbit", "pulse")
KINDS = ("object","airflow","heat","force","light","electricity")
BACKGROUNDS = ((15,74,68),(122,56,25),(84,31,69),(118,32,42),(39,65,112),(99,80,21))


@lru_cache(maxsize=24)
def _headline_font(size):
    path = Path(__file__).resolve().parent/"assets/fonts/barlow-condensed/BarlowCondensed-Black.ttf"
    return ImageFont.truetype(str(path),size)


STORYBOARD_INSTRUCTIONS = """For Reel motion, include one or two objects with each narration beat,
including hook_objects for the hook. These will be separate realistic cutout photographs.
Choose the exact visible object doing what this beat describes. Include its whole recognizable
form when the whole system moves. Keep its name the same in later beats to reuse the same image.
Use at most six unique objects for the video. Describe each photograph in 10 to 25 concrete
words using physical appearance and material. The avoid field lists likely wrong objects.
Set kind to object for physical things and give a short English photographic search_query,
such as hot air balloon. Set kind to airflow, heat, force, light or electricity for invisible
processes, with an empty search_query. Those use animated visual effects, not object photographs.
For each physical object, choose its effect field explicitly. Use heat while heating, airflow
for flowing air, force for a push or lift, electricity for current, and light for illumination.
Use none when no such process is described. Effects follow the moving object and need no photo.
Never request photographs of abstract blocks or spheres to represent these processes.
Keep heads, hands or figures only when they belong in the explanation.
The primary object should fill the center. Use left and right for a comparison.
Actions must agree with that beat's narration. lift moves up, lower moves down,
slide-left and slide-right move sideways, rotate turns the object, pulse gently changes
its size, orbit moves along a small oval, and hold leaves the object steady.
Use meaningful actions to show the changes the narration describes. Use the physical objects
the explanation actually needs. When an object changes form, give its new form a different name
and replace the old asset in that beat. Put backgrounds before foreground objects.
Use objects whose literal appearance can explain the mechanism. Keep each important object visible."""

def motion_objects_schema():
    properties = {"name":{"type":"string"},"description":{"type":"string"},"avoid":{"type":"string"},
                  "kind":{"type":"string","enum":list(KINDS)},"search_query":{"type":"string"},
                  "effect":{"type":"string","enum":["none",*KINDS[1:]]},
                  "position":{"type":"string","enum":list(POSITIONS)},
                  "size":{"type":"string","enum":list(SIZES)},
                  "action":{"type":"string","enum":list(ACTIONS)}}
    return {"type":"array","minItems":1,"maxItems":2,
            "items":{"type":"object","properties":properties,"required":list(properties)}}


def motion_plan_from_scenes(scenes):
    assets = {}
    shots = []
    for scene in scenes:
        layers = []
        for item in scene["objects"]:
            key = item["name"].strip().casefold()
            assets.setdefault(key,{"name":item["name"],"description":item["description"],"avoid":item["avoid"],
                                   "kind":item.get("kind","object"),"search_query":item.get("search_query",item["name"])})
            layers.append({"asset":assets[key]["name"],"position":item["position"],
                           "size":item["size"],"action":item["action"]})
            effect = item.get("effect","none")
            if effect != "none":
                if effect not in KINDS[1:]:
                    raise ValueError("Unknown process effect")
                effect_key = key+"::"+effect
                assets.setdefault(effect_key,{"name":f"{effect} {len(assets)}",
                    "description":f"Animated {effect} on {item['name']}","kind":effect,"search_query":""})
                layers.append({**layers[-1],"asset":assets[effect_key]["name"]})
        shots.append({"layers":layers})
    return read_motion_plan({"assets":list(assets.values()),"scenes":shots},len(scenes))


@dataclass(frozen=True)
class Asset:
    name: str
    description: str
    avoid: str = ""
    kind: str = "object"
    query: str = ""


@dataclass(frozen=True)
class Layer:
    asset: str
    position: str
    size: str
    action: str


def read_motion_plan(data, beats):
    assets = []
    by_name = {}
    for item in data["assets"]:
        name,description = item["name"].strip(),item["description"].strip()
        if not 1 <= len(name) <= 48 or not 8 <= len(description) <= 350 or name.casefold() in by_name:
            raise ValueError("Each visual asset needs a distinct name and physical description")
        by_name[name.casefold()] = name
        kind = item.get("kind","object")
        if kind not in KINDS:
            raise ValueError("Unknown visual effect kind")
        assets.append(Asset(name,description,item.get("avoid","")[:220],kind,item.get("search_query",name)[:100]))
    if not 1 <= len(assets) <= 20:
        raise ValueError("Use at most twenty object and process layers")
    if len(data["scenes"]) != beats:
        raise ValueError("Every narration beat needs a scene")
    scenes = []
    for scene in data["scenes"]:
        layers = []
        for item in scene["layers"]:
            name,position,size,action = (item[key].strip() for key in ("asset","position","size","action"))
            if name.casefold() not in by_name or position not in POSITIONS or size not in SIZES or action not in ACTIONS:
                raise ValueError("A visual layer has an unknown asset, placement, size or action")
            layers.append(Layer(by_name[name.casefold()],position,size,action))
        scenes.append(layers)
    if any(not 1 <= len(scene) <= 4 or len({layer.asset for layer in scene}) != len(scene) for scene in scenes):
        raise ValueError("Every narration beat needs one to four distinct visible layers")
    kinds = {asset.name:asset.kind for asset in assets}
    if not any(layer.action != "hold" or kinds[layer.asset] != "object" for scene in scenes[1:] for layer in scene):
        raise ValueError("Show the narrated process with at least one moving object")
    used = {layer.asset for scene in scenes for layer in scene}
    return tuple(asset for asset in assets if asset.name in used), tuple(tuple(scene) for scene in scenes)


@lru_cache(maxsize=1)
def _segmentation_session():
    from onnxruntime import InferenceSession, SessionOptions
    directory = Path(__file__).resolve().parent/".visual-engine"
    model = directory/"u2netp.onnx"
    if not model.is_file():
        directory.mkdir(exist_ok=True)
        descriptor,temporary = tempfile.mkstemp(prefix="cutout-",suffix=".part",dir=directory)
        try:
            address = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx"
            with os.fdopen(descriptor,"wb") as target, urlopen(address,timeout=45) as source:
                while chunk := source.read(65536):
                    target.write(chunk)
            if md5(Path(temporary).read_bytes()).hexdigest() != "8e83ca70e441ab06c318d82300c84806":
                raise ValueError("The downloaded cutout model failed its file check")
            os.replace(temporary,model)
        except Exception:
            Path(temporary).unlink(missing_ok=True)
            raise VisualUnavailable("Could not install the small cutout model. Check the connection and try again.") from None
    options = SessionOptions()
    options.intra_op_num_threads = 2
    return InferenceSession(str(model),options,providers=["CPUExecutionProvider"])


def extract_cutout(picture):
    """Separate a photographic object from its background using a local saliency model."""
    session = _segmentation_session()
    reduced = np.asarray(picture.convert("RGB").resize((320,320),Image.Resampling.LANCZOS),dtype=np.float32)
    normalized = reduced/max(float(reduced.max()),1e-6)
    normalized = (normalized-np.array((.485,.456,.406)))/np.array((.229,.224,.225))
    tensor = normalized.transpose((2,0,1))[None].astype(np.float32)
    prediction = session.run(None,{session.get_inputs()[0].name:tensor})[0][0,0]
    spread = float(prediction.max()-prediction.min())
    if spread < 1e-6:
        raise VisualUnavailable("The cutout model could not identify this object. Try generating again.")
    mask = np.clip((prediction-prediction.min())/spread,0,1)
    alpha = Image.fromarray((mask*255).astype("uint8")).resize(picture.size,Image.Resampling.LANCZOS)
    alpha = np.asarray(alpha)
    # Keep small image-model specks out of the silhouette.
    count, pieces, stats, _ = cv2.connectedComponentsWithStats((alpha > 90).astype("uint8"))
    if count <= 1:
        raise VisualUnavailable("The image model returned an empty object. Try generating again.")
    largest = int(stats[1:,cv2.CC_STAT_AREA].max())
    keep = 1+np.flatnonzero(stats[1:,cv2.CC_STAT_AREA] >= max(40,largest*.002))
    region = cv2.dilate(np.isin(pieces,keep).astype("uint8"),np.ones((5,5),dtype="uint8"))
    alpha = (alpha*region).astype("uint8")
    mask = Image.fromarray(alpha).filter(ImageFilter.GaussianBlur(.7))
    box = mask.getbbox()
    if not box or (box[2]-box[0])*(box[3]-box[1]) < picture.width*picture.height*.035:
        raise VisualUnavailable("The image model did not create a clear object. Try naming the object more precisely.")
    result = picture.convert("RGBA")
    result.putalpha(mask)
    return result.crop(box)


def _ease(fraction):
    x = min(1.,max(0.,fraction))
    return x*x*x*(10+x*(-15+6*x))


def _mix(a,b,amount):
    return tuple(x+(y-x)*amount for x,y in zip(a,b))


def _pose(layer, progress):
    x,y = POSITIONS[layer.position]
    size = SIZES[layer.size]
    angle = 0.
    motion = _ease((progress-.10)/.74)
    if layer.action == "lower":
        y += .15*motion
    elif layer.action == "lift":
        y -= .15*motion
    elif layer.action == "slide-left":
        x -= .20*motion
    elif layer.action == "slide-right":
        x += .20*motion
    elif layer.action == "rotate":
        angle = -360*motion
    elif layer.action == "orbit":
        x += .08*sin(2*pi*motion)
        y += .035*(cos(2*pi*motion)-1)
    elif layer.action == "pulse":
        size *= 1.+.045*sin(4*pi*motion)
    return x,y,size,angle


@lru_cache(maxsize=12)
def _background(size, color):
    width,height = size
    y,x = np.mgrid[0:height,0:width]
    glow = np.exp(-((x/width-.45)**2*3+(y/height-.43)**2*2))
    shade = .22+.78*glow
    base = np.asarray(color)
    pixels = np.clip(shade[...,None]*base+glow[...,None]*23,0,255).astype("uint8")
    frame = Image.fromarray(pixels).convert("RGBA")
    overlay = Image.new("RGBA",size)
    draw = ImageDraw.Draw(overlay)
    draw.line((width*.06,height*.82,width*.94,height*.82),fill=(255,255,255,35),width=1)
    frame.alpha_composite(overlay)
    return frame


class MotionReel:
    def __init__(self, plan, pictures, scenes, size):
        self.assets, self.layers = plan
        self.pictures = pictures
        self.scenes = scenes
        self.size = size
        self.cache = {}
        self.kinds = {asset.name:asset.kind for asset in self.assets}

    def _sprite(self, name, scale, angle, opacity):
        # Cache resized silhouettes and shadows, including repeated objects across beats.
        key = (name,round(scale*self.size[0]),round(angle*2)/2)
        if key not in self.cache:
            source = self.pictures[name]
            width = max(2,key[1])
            source = source.resize((width,max(2,round(width*source.height/source.width))),Image.Resampling.LANCZOS)
            # Fit tall props into the central stage as well as fitting their widths.
            if source.height > self.size[1]*.49:
                source.thumbnail((width,round(self.size[1]*.49)),Image.Resampling.LANCZOS)
            rotated = source.rotate(key[2],resample=Image.Resampling.BICUBIC,expand=True)
            padding = round(self.size[0]*.025)
            sprite = Image.new("RGBA",(rotated.width+padding*2,rotated.height+padding*2))
            sprite.alpha_composite(rotated,(padding,padding))
            shadow = Image.new("RGBA",sprite.size,(0,0,0,0))
            shadow.putalpha(sprite.getchannel("A").point(lambda alpha: round(alpha*.36)))
            shadow = shadow.filter(ImageFilter.GaussianBlur(self.size[0]*.013))
            self.cache[key] = sprite,shadow
            if len(self.cache)>80:
                self.cache.pop(next(iter(self.cache)))
        sprite,shadow = self.cache[key]
        if opacity >= .999:
            return sprite,shadow
        faded = sprite.copy()
        faded.putalpha(faded.getchannel("A").point(lambda alpha: round(alpha*opacity)))
        shade = shadow.copy()
        shade.putalpha(shade.getchannel("A").point(lambda alpha: round(alpha*opacity)))
        return faded,shade

    def frame(self, beat, fraction, subtitle):
        width,height = self.size
        arrival = _ease(fraction/.095)
        color = BACKGROUNDS[beat%len(BACKGROUNDS)]
        frame = _background(self.size,color).copy()
        if beat and arrival < 1:
            old = _background(self.size,BACKGROUNDS[(beat-1)%len(BACKGROUNDS)])
            frame = Image.blend(old,frame,arrival)
        previous = {layer.asset:layer for layer in self.layers[beat-1]} if beat else {}
        current = {layer.asset for layer in self.layers[beat]}
        items = []
        # Departing objects slide out as new objects arrive. Shared objects keep their pose.
        for name,layer in previous.items():
            if name in current or arrival >= 1:
                continue
            x,y,size,angle = _pose(layer,1.)
            items.append((name,(x-.18*arrival,y,size,angle),1.-arrival,1.))
        for index,layer in enumerate(self.layers[beat]):
            pose = _pose(layer,fraction)
            if layer.asset in previous:
                pose = _mix(_pose(previous[layer.asset],1.),pose,arrival)
                opacity = 1.
            else:
                x,y,size,angle = pose
                pose = (x+.18*(1.-arrival),y+.025*(1.-arrival),size,angle)
                opacity = arrival
            items.append((layer.asset,pose,opacity,fraction))
        # Explanatory flow and heat stay visible over the photographic objects.
        for item in sorted(items,key=lambda item:self.kinds[item[0]] != "object"):
            self._composite(frame,*item)
        title = self.scenes[beat]["heading"]
        if beat and arrival < 1:
            self._headline(frame,self.scenes[beat-1]["heading"],1.-arrival)
        self._headline(frame,title,arrival)
        if subtitle:
            # Keep the stage and the captions from overlapping.
            layer, _ = subtitle
            frame.alpha_composite(layer,(0,round(height*.77)))
        return frame.convert("RGB")

    def _composite(self, frame, name, pose, opacity, fraction):
        x,y,size,angle = pose
        if self.kinds[name] != "object":
            effect = self._effect(self.kinds[name],fraction)
            effect = effect.resize((max(2,round(size*self.size[0])),)*2,Image.Resampling.BICUBIC)
            effect.putalpha(effect.getchannel("A").point(lambda alpha:round(alpha*opacity)))
            frame.alpha_composite(effect,(round(x*self.size[0]-effect.width/2),round(y*self.size[1]-effect.height/2)))
            return
        sprite,shadow = self._sprite(name,size,angle,opacity)
        width,height = self.size
        location = (round(x*width-sprite.width/2),round(y*height-sprite.height/2))
        frame.alpha_composite(shadow,(location[0]+round(width*.016),location[1]+round(height*.012)))
        frame.alpha_composite(sprite,location)

    def _effect(self, kind, fraction):
        effect = Image.new("RGBA",(256,256))
        draw = ImageDraw.Draw(effect)
        color = (255,154,71,205) if kind == "heat" else (110,236,255,205)
        if kind in ("force","light","electricity"):
            for index in range(3):
                x = 60+index*68
                draw.line((x,212,x,50),fill=color,width=5)
                draw.polygon(((x,35),(x-13,62),(x+13,62)),fill=color)
        else:
            for index in range(5):
                points = [(28+index*48+9*sin(y*.045+fraction*4*pi),y) for y in range(40,220,4)]
                draw.line(points,fill=color,width=4,joint="curve")
                x,y = points[0]
                draw.line((x-8,y+12,x,y,x+8,y+12),fill=color,width=3)
        for index in range(8):
            y = 225-((fraction*2+index/8)%1)*190
            x = 32+(index%5)*46+7*sin(y*.04)
            draw.ellipse((x-3,y-3,x+3,y+3),fill=color)
        return effect

    def _headline(self, frame, title, arrival):
        width,height = self.size
        title = re.sub(r"\s+"," ",title).strip().upper()
        font_size = round(width*.086)
        layer = Image.new("RGBA",self.size)
        draw = ImageDraw.Draw(layer)
        while True:
            font = _headline_font(font_size)
            lines = [""]
            for word in title.split():
                line = (lines[-1]+" "+word).strip()
                if lines[-1] and font.getlength(line)>width*.88:
                    lines.append(word)
                else:
                    lines[-1] = line
            if len(lines) <= 3 or font_size < width*.05:
                break
            font_size -= 2
        spacing = round(font_size*1.12)
        top = round(height*.085-(1.-arrival)*height*.02)
        for index,line in enumerate(lines):
            color = (255,224,133) if index else (255,247,235)
            alpha = round(255*arrival)
            draw.text((width*.07,top+index*spacing),line,font=font,fill=(*color,alpha),
                      stroke_width=max(1,round(width*.003)),stroke_fill=(24,35,35,alpha),anchor="lt")
        frame.alpha_composite(layer)
