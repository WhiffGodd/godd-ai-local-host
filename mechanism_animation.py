# SPDX-License-Identifier: MIT
"""Animate a model-planned cutaway using validated drawing and motion data."""

from dataclasses import dataclass
from functools import lru_cache
from math import cos, dist, radians, sin, tau
import re

from PIL import Image, ImageColor, ImageDraw

from cinematic_render import _part_badge
from explainer_parts import Part


PALETTE = {
    "steel": "#91aabd", "dark": "#30485f", "white": "#edf3e9", "gold": "#eab15b",
    "red": "#fa7869", "blue": "#55aafe", "cyan": "#60e0eb", "green": "#82d393",
}
SHAPES = ("plate", "contour", "oval", "gear", "pipe", "spring", "path")
EFFECTS = ("move", "turn", "expand", "flow", "energize")


def _object(**fields):
    return {"type": "object", "properties": fields, "required": list(fields)}


def mechanism_schema(beats):
    return _object(
        parts={"type": "array", "minItems": 3, "maxItems": 12, "items": {"type": "string"}},
        actions={"type": "array", "minItems": 3, "maxItems": 18, "items": {"type": "string"},
                 "description": f"Actions must reference narration beats 1 through {beats-1}."},
    )


PLAN_INSTRUCTIONS = """Design an accurate continuous animated cutaway for the requested explainer.
Draw the actual device in one side view with its long axis filling much of the frame.
Use ONE 0..100 coordinate system for the whole device, with (0,0) at the upper left and y going DOWN.
Span at least 50 units horizontally or vertically. For example, a horizontal handle running
from x=15 to x=85 must actually have vertices near x=15 and x=85. Give main components
their real relative sizes and leave room for the full range of motion from 8 to 92.
Parts draw back to front. Do not reduce distinctive parts to small squares.
Use at least three distinct functional parts plus shaped housing or supports when appropriate.
For a biological, electrical, or other non-mechanical process use the real structures,
materials, signals, and pathways. Add only elements that belong to the system.
Arrange parts at true contact points, pivots, and connections. Match the nouns in the narration.
Use a plate for a two-corner rectangular component, an oval or gear for a two-corner bounding box,
a contour for a closed polygon with 3..18 absolute outline points, a pipe or path for connected
centerline points, and a spring for two endpoints. Use contours with recognizable profiles for
irregular parts. Give all parts a pivot in board coordinates. Make the cutaway large and readable.
An action is a change on a 1-based narration beat after the hook, with a start and end fraction
between 0 and 1. Spread the events across the narration in order. Include at least three animated beats.
For move, amount is [dx,dy] in board units. For turn, use [clockwise degrees,0].
For expand, amount is [relative x scale,relative y scale], e.g. [1,0.6] to compress vertically.
Move, turn and expand changes remain applied in following beats. Apply matching changes to parts
that move together, and use small amounts so pieces stay connected. Only flow is temporary.
For flow animate particles along the points of a pipe or path in their listed order; amount [-1,0]
reverses the flow. For energize, [1,0] turns on the heat, light, or pressure color and
[0,0] turns it back off. The color persists until the next energize action on that part.
Illustrate the causal chain from input through each meaningful change to the resulting output. Each action
must depict what happens in its matching narration beat. Treat each independently moving subpart
as its own shape, with a pivot at its actual hinge. Keep a fixed base or casing as a frame of reference.
For example, a sliding gate could use a fixed track from [12,70] to [88,75], a gate with
outline [[25,40],[59,40],[59,68],[25,68]], and a cylinder behind it on the left.
Moving the gate by [20,0] shifts it along the track; its upright outline doesn't turn.
The example demonstrates coordinates only. Design the specific object in this prompt.
Return JSON with two arrays of short strings called parts and actions.
Part row: name|shape|color|pivotX,pivotY|pointX,pointY pointX,pointY ...
Example: Track|plate|steel|50,72|12,70 88,75
Colors: steel, dark, white, gold, red, blue, cyan, green.
Action row: beat|part name|effect|amountX,amountY|start,end
Example: 2|Gate|move|20,0|0.10,0.70
Keep all rows in that syntax. Use a space between coordinate pairs and no extra commentary.
Supply data only. Follow provider safety rules and keep explanations non-actionable for harmful topics."""


def _pair(value, lower, upper):
    if (not isinstance(value, list) or len(value) != 2
            or any(type(item) not in (float, int) or not lower <= item <= upper for item in value)):
        raise ValueError("Invalid mechanism coordinates")
    return tuple(value)


def _name(value):
    return " ".join(value.replace("_", " ").split())[:42]


@dataclass(frozen=True)
class Component:
    part: Part
    shape: str
    color: str
    pivot: tuple
    points: tuple


@dataclass(frozen=True)
class Action:
    beat: int
    part: str
    effect: str
    amount: tuple
    start: float
    end: float


def read_mechanism(data, beats):
    entries, events = data["parts"], data["actions"]
    if (not isinstance(entries,list) or not isinstance(events,list)
            or not 3 <= len(entries) <= 12 or not 3 <= len(events) <= 18):
        raise ValueError("Invalid mechanism size")
    components = {}
    for item in entries:
        name = _name(item["name"])
        shape = item["shape"]
        pivot = _pair(item["pivot"], 0, 100)
        points = tuple(_pair(point, 0, 100) for point in item["points"])
        if (not name or name.casefold() in components or shape not in SHAPES or not 2 <= len(points) <= 18
                or (shape == "contour" and len(points) < 3) or len(set(points)) < 2):
            raise ValueError("Invalid mechanism component")
        if shape in ("plate","gear","oval") and any(len(set(axis)) < 2 for axis in zip(*points)):
            raise ValueError("A filled shape needs width and height")
        alias = re.escape(name) + ("" if name.endswith("s") else "s?")
        label = name[0].upper()+name[1:]
        part = Part(label, (label,), "detail", alias)
        components[name.casefold()] = Component(part, shape, PALETTE[item["color"]], pivot, points)
    actions = []
    for item in events:
        beat, effect = item["beat"], item["effect"]
        name = _name(item["part"]).casefold()
        amount = _pair(item["amount"], -720, 720)
        start, end = _pair([item["start"], item["end"]], 0, 1)
        if (type(beat) is not int or not 1 <= beat < beats or name not in components
                or effect not in EFFECTS or start >= end):
            raise ValueError("Invalid mechanism action")
        if effect == "move" and max(map(abs, amount)) > 55:
            raise ValueError("Invalid travel distance")
        if effect == "expand" and any(not .25 <= value <= 2.5 for value in amount):
            raise ValueError("Invalid scale")
        if ((effect == "move" and amount == (0,0)) or (effect == "turn" and not amount[0])
                or (effect == "expand" and amount == (1,1))):
            continue
        if effect == "flow" and components[name].shape not in ("pipe", "path"):
            raise ValueError("Flow needs a connected route")
        if effect == "energize" and not 0. <= amount[0] <= 1.:
            raise ValueError("Invalid heat, light, or pressure level")
        actions.append(Action(beat, components[name].part.label, effect, amount, start, end))
    if len({action.beat for action in actions}) < 3 or all(action.effect == "energize" for action in actions):
        raise ValueError("The animation needs at least three moving beats")
    actions.sort(key=lambda action: (action.beat, action.start, action.end))
    mechanism = tuple(components.values()), tuple(actions)
    l,t,r,b = _bounds(mechanism)
    if min(l,t) < -30 or max(r,b) > 130:
        raise ValueError("A moving part exceeds the cutaway area")
    initial = [point for item in mechanism[0] for point in _outline(item)]
    x,y = zip(*initial)
    if max(max(x)-min(x),max(y)-min(y)) < 34:
        raise ValueError("The parts are too small and cramped to show a mechanism")
    return mechanism


def parse_mechanism_rows(data, beats):
    def pair(text):
        return [float(value) for value in text.split(",")]

    parts = []
    for row in data["parts"]:
        name,shape,color,pivot,points = (value.strip() for value in row.split("|"))
        parts.append({"name":name,"shape":shape,"color":color,"pivot":pair(pivot),
                      "points":[pair(point) for point in points.split()]})
    actions = []
    for row in data["actions"]:
        beat,part,effect,amount,timing = (value.strip() for value in row.split("|"))
        start,end = pair(timing)
        actions.append({"beat":int(beat),"part":part,"effect":effect,"amount":pair(amount),"start":start,"end":end})
    return read_mechanism({"parts":parts,"actions":actions},beats)


def motion_state(events, beat, fraction):
    dx = dy = turn = heat = flow = 0.
    sx = sy = 1.
    for action in events:
        if action.beat > beat:
            continue
        p = 1. if action.beat < beat else min(1.,max(0.,(fraction-action.start)/(action.end-action.start)))
        eased = p*p*(3-2*p)
        x, y = action.amount
        if action.effect == "move":
            dx, dy = dx+x*eased, dy+y*eased
        elif action.effect == "turn":
            turn += radians(x)*eased
        elif action.effect == "expand":
            sx, sy = sx*(1+(x-1)*eased), sy*(1+(y-1)*eased)
        elif action.effect == "energize":
            heat += (x-heat)*eased
        elif 0. < p < 1.:
            flow = p if x >= 0 else -p
    return dx,dy,turn,sx,sy,heat,flow


def _transform(component, events, beat, fraction):
    dx,dy,turn,sx,sy,heat,flow = motion_state(events,beat,fraction)
    px, py = component.pivot
    c, s = cos(turn), sin(turn)
    points = []
    for x,y in _outline(component):
        local_x, local_y = (x-px)*sx, (y-py)*sy
        points.append((px+dx+c*local_x-s*local_y,py+dy+s*local_x+c*local_y))
    return points, (px+dx,py+dy), heat, flow


@lru_cache(maxsize=96)
def _outline(component):
    points = component.points
    if component.shape in ("contour","path","pipe"):
        return points
    if component.shape == "plate":
        x,y,x2,y2 = _envelope(points)
        return ((x,y),(x2,y),(x2,y2),(x,y2))
    if component.shape == "spring":
        (x,y),(x2,y2) = points[:2]
        length = max(dist((x,y),(x2,y2)),.01)
        return tuple((x+(x2-x)*i/19-(y2-y)/length*(3 if i%2 else -3),
                      y+(y2-y)*i/19+(x2-x)/length*(3 if i%2 else -3)) for i in range(20))
    x,y,x2,y2 = _envelope(points)
    count = 56 if component.shape == "gear" else 40
    radius = lambda i: .83 if component.shape == "gear" and i % 4 in (0,3) else 1.
    return tuple(((x+x2)/2+(x2-x)/2*cos(tau*i/count)*radius(i),
                  (y+y2)/2+(y2-y)/2*sin(tau*i/count)*radius(i)) for i in range(count))


@lru_cache(maxsize=8)
def _bounds(mechanism):
    parts, actions = mechanism
    points = []
    for component in parts:
        events = tuple(action for action in actions if action.part == component.part.label)
        points.extend(_outline(component))
        for action in events:
            for index in range(9):
                fraction = action.start+(action.end-action.start)*index/8
                points.extend(_transform(component,events,action.beat,fraction)[0])
    return _envelope(points)


def _envelope(points):
    x,y = zip(*points)
    return min(x),min(y),max(x),max(y)


@lru_cache(maxsize=3)
def _background(size):
    width,height = size
    image = Image.new("RGB",size)
    draw = ImageDraw.Draw(image)
    for y in range(height):
        light = 1.-abs(y/height-.50)*1.6
        draw.line((0,y,width,y),fill=(round(8+9*light),round(14+15*light),round(27+22*light)))
    tick = max(12,width//30)
    for y in range(round(height*.21),round(height*.68),tick):
        for x in range(tick,width,tick):
            draw.point((x,y),fill="#38475a")
    return image


@lru_cache(maxsize=16)
def _rgb(color):
    return ImageColor.getrgb(color)


class MechanismShot:
    def __init__(self, mechanism, size, beat):
        parts, actions = mechanism
        self.size = size
        self.beat = beat
        self.components = [(item,tuple(action for action in actions if action.part == item.part.label))
                           for item in parts]
        self.actions = tuple(action for action in actions if action.beat == beat)
        l,t,r,b = _bounds(mechanism)
        width,height = size
        self.zoom = min(width*.83/max(r-l,1.),height*.41/max(b-t,1.))
        self.center = ((l+r)/2,(t+b)/2)

    def frame(self, fraction, subtitle, part=None):
        frame = _background(self.size).copy()
        draw = ImageDraw.Draw(frame)
        width,height = self.size
        radius = max(3,width//135)
        motion = next((action for action in self.actions if action.start <= fraction <= action.end), None)
        active = motion.part if motion else part.label if part else ""
        target = None
        def pixel(point):
            x,y = point
            return (width*.5+(x-self.center[0])*self.zoom,
                    height*.445+(y-self.center[1])*self.zoom)

        for item, actions in self.components:
            points, center, heat, flow = _transform(item, actions, self.beat, fraction)
            points = [pixel(point) for point in points]
            color = tuple(round(c+(h-c)*heat) for c,h in zip(_rgb(item.color),(255,154,92)))
            accent = "#75f3ff" if active == item.part.label else "#b9cfdb"
            if item.shape in ("pipe","spring","path"):
                stroke = radius*(5 if item.shape == "pipe" else 2)
                draw.line(points,fill="#0b1522",width=stroke+2*radius,joint="curve")
                draw.line(points,fill=color,width=stroke,joint="curve")
                if flow:
                    lengths = [dist(a,b) for a,b in zip(points,points[1:])]
                    total = sum(lengths)
                    head = radius * min(1., abs(flow)*7, (1.-abs(flow))*7)
                    for dot in range(6):
                        remaining = ((flow*2+dot/6) % 1.)*total
                        for a,b,length in zip(points,points[1:],lengths):
                            if length and remaining <= length:
                                cx,cy = (u+(v-u)*remaining/length for u,v in zip(a,b))
                                draw.ellipse((cx-head,cy-head,cx+head,cy+head),fill="#efffff")
                                break
                            remaining -= length
            else:
                draw.polygon([(x+radius,y+radius*2) for x,y in points],fill="#0a1423")
                draw.polygon(points,fill=color)
                draw.line([*points,points[0]],fill=accent,width=radius//2+1,joint="curve")
                if item.shape == "gear":
                    x,y = pixel(center)
                    draw.ellipse((x-radius*2,y-radius*2,x+radius*2,y+radius*2),fill="#18283b",outline=accent)
            if active == item.part.label:
                if item.shape in ("pipe", "spring", "path"):
                    a,b = points[(len(points)-1)//2:][:2]
                    target = ((a[0]+b[0])/2,(a[1]+b[1])/2)
                else:
                    target = tuple(sum(axis)/len(points) for axis in zip(*points))
        if target:
            layer, (x,y) = _part_badge(active,self.size)
            frame.paste(layer,(x,y),layer)
        if subtitle:
            frame.paste(subtitle[0],subtitle[1],subtitle[0])
        return frame
