# SPDX-License-Identifier: MIT
"""Animate a model-planned cutaway using validated drawing and motion data."""

from dataclasses import dataclass
from functools import lru_cache
from math import cos, dist, isfinite, radians, sin, tau
import re

from PIL import Image, ImageColor, ImageDraw

from cinematic_render import _part_badge
from explainer_parts import Part
from biological_components import BIOLOGICAL_SHAPES
from solid_geometry import read_solids


PALETTE = {
    "steel": "#91aabd", "dark": "#30485f", "white": "#edf3e9", "gold": "#eab15b",
    "red": "#fa7869", "blue": "#55aafe", "cyan": "#60e0eb", "green": "#82d393",
    "tissue":"#bf7970", "blood":"#b83143", "bone":"#e8dfc7", "purple":"#9d7eb4",
}
ELECTRICAL_SHAPES = ("wire", "battery", "bulb", "led", "resistor", "capacitor", "coil", "motor", "terminal", "relay", "switch")
SHAPES = ("solid", "plate", "contour", "oval", "gear", "pipe", "spring", "path", *ELECTRICAL_SHAPES, *BIOLOGICAL_SHAPES)
EFFECTS = ("move", "turn", "spin", "expand", "flow", "energize", "current", "charge", "switch", "dissolve", "pulse")


def _object(**fields):
    return {"type": "object", "properties": fields, "required": list(fields)}


def mechanism_schema(beats):
    pair = {"type":"array", "items":{"type":"number"}, "minItems":2, "maxItems":2}
    coordinate = {**pair, "items":{"type":"number","minimum":0,"maximum":100}}
    amount = {**pair, "items":{"type":"number","minimum":-720,"maximum":720}}
    return _object(
        parts={"type": "array", "minItems": 3, "maxItems": 24, "items": _object(
            name={"type":"string"}, shape={"type":"string","enum":list(SHAPES)},
            color={"type":"string","enum":list(PALETTE)}, pivot=coordinate,
            points={"type":"array","minItems":2,"maxItems":48,"items":coordinate})},
        actions={"type": "array", "minItems": 3, "maxItems": 64, "items": _object(
            beat={"type":"integer","minimum":1,"maximum":beats-1}, part={"type":"string"},
            effect={"type":"string","enum":list(EFFECTS)}, amount=amount,
            start={"type":"number","minimum":0,"maximum":.9}, end={"type":"number","minimum":.05,"maximum":1}),
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
a contour for a closed polygon with 3..48 absolute outline points, a pipe or path for connected
centerline points, and a spring for two endpoints. Use contours with recognizable profiles for
irregular parts. Give all parts a pivot in board coordinates. Make the cutaway large and readable.
An action is a change on a 1-based narration beat after the hook, with a start and end fraction
between 0 and 1. Start MUST be strictly less than end. Use start 0.1, end 0.8 when unsure.
Never use a zero-length interval or zero movement as a placeholder. Omit inactive actions.
Spread the events across the narration in order. Include at least three animated beats.
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
Return JSON with arrays of OBJECTS called parts and actions, following the supplied schema.
Example part: {"name":"Track","shape":"plate","color":"steel","pivot":[50,72],"points":[[12,70],[88,75]]}.
Example action: {"beat":2,"part":"Gate","effect":"move","amount":[20,0],"start":0.1,"end":0.7}.
Electrical components available: wire, battery, bulb, led, resistor, capacitor, coil, motor,
terminal, relay and switch. Use their real shapes instead of generic colored blocks.
These are detailed manufactured components: marked battery cells, electrolytic capacitor cans
with radial leads and polarity stripes, banded axial resistors, glass bulbs, and insulated cables.
Always include a native battery/capacitor/etc for each complete physical component requested.
Do not substitute two floating rectangles for a capacitor or a block for a battery.
Use a detail view to expose the battery/capacitor internals while keeping their physical case.
Wire has a copper conductor, stripped ends, insulated jacket and smooth bends. Name return
and negative wires explicitly. Use the wire shape for electrical connections, not a plate.
Wire takes an ordered centerline. All other electrical shapes take two bounding-box corners.
Battery terminals are top/bottom center (+ at top); other electrical terminals are left/right center.
Capacitor lead adapters reach left/right center (positive left, negative right); its actual leads exit the bottom.
Connect wire endpoints EXACTLY to these terminal positions. Never short the battery.
Use separate movable contours for a switch blade, relay armature, and attached contacts.
A switch shape is its FIXED insulated base and end contacts; its blade must be a separate part.
Motor has a visible rotor: turn actions rotate its rotor only. Coil shows actual copper windings.
For current on wire/path/pipe, amount [level,0] persists between beats: +1 follows listed points,
-1 reverses direction, 0 stops. Set EVERY series wire to zero when the switch opens.
Flow is temporary; use current for continuing electrical current. Energize controls filament/LED glow.
Do not animate current across an open contact. Voltage may exist while current is zero.
Electron drift is opposite conventional current. Do not describe energy as fast electrons.
This is a qualitative educational animation, not a circuit solver; do not invent measured values.
Biology components: tablet, capsule, esophagus, stomach, intestine, villus, blood_vessel,
red_blood_cell, liver, kidney, ureter, bladder, heart, lung, alveolus, cell, membrane, receptor, neuron, torso,
food_bolus. Use these anatomical meshes rather than colored blocks. All take two bounding-box
corners, except blood_vessel, which can take an ordered centerline. Esophagus ports are top/bottom
center; blood vessels with two corners run left/right through the box center.
For dissolve use [fraction,0], from 0 intact to 1 dissolved, on tablet/capsule only. It persists.
For pulse use [cycles per second,amplitude], e.g. [1,0.06], on biological parts only.
Flow follows a blood vessel, esophagus, intestine or neuron route. Show absorption as movement
of dissolved molecule markers through a lining; never pass an intact pill into a blood vessel.
The illustrated oral-medicine route is gut -> portal blood -> liver -> systemic blood -> tissue.
Do not invent a specific medicine's mechanism, dose, treatment claim or timing. Different
formulations and medicines behave differently. Use neutral educational descriptions.
Supply data only. Follow provider safety rules and keep explanations non-actionable for harmful topics."""


def _pair(value, lower, upper, field='Coordinate pair'):
    if (not isinstance(value, list) or len(value) != 2
            or any(type(item) not in (float, int) or not lower <= item <= upper or not isfinite(item) for item in value)):
        raise ValueError(f"{field} must be [x,y] with two finite numbers from {lower} to {upper}; received {value!r}")
    return tuple(value)


def _name(value):
    return " ".join(value.replace("_", " ").split())[:42]


def _electrical_shape(name, shape):
    """Do not turn a complete named electrical component into a generic block.

    Preserve separately modeled subparts such as contacts and capacitor plates.
    """
    if shape=='wire':return shape  # A routed conductor never becomes a complete device by its label.
    if shape in ELECTRICAL_SHAPES and not re.fullmatch(
            r'(?:battery|resistor|capacitor|switch|bulb|led|motor|coil|relay)(?: \d+)?',name,re.I):
        return shape
    if re.search(r'\b(?:terminal|filament|plate|electrode|contact|shaft|blade|housing|core|cover|lead|brush|armature|rotor|stator|magnet)\b',name,re.I):
        return shape
    for pattern,native in ((r'\b(?:batter(?:y|ies)|battery cell)\b','battery'),
                           (r'\bcapacitors?\b','capacitor'),(r'\bresistors?\b','resistor'),
                           (r'\bled\b','led'),(r'\b(?:lightbulb|bulb|lamp)s?\b','bulb'),
                           (r'\b(?:electric |DC )?motor\b','motor'),(r'\b(?:coil|solenoid|winding)s?\b','coil')):
        if re.search(pattern,name,re.I):
            return native
    if re.fullmatch(r'(?:control |power |toggle )?switch(?: base)?',name,re.I):
        return 'switch'
    if shape in ('pipe','path') and re.search(r'\b(?:wire|cable)s?\b',name,re.I):
        return 'wire'
    return shape


def _biological_shape(name,shape):
    if shape in BIOLOGICAL_SHAPES:
        return shape
    if re.search(r'\b(?:cell|plasma|lipid) membrane\b',name,re.I):
        return 'membrane'
    if re.fullmatch(r'(?:target |cell |protein )?receptor',name,re.I):
        return 'receptor'
    if re.fullmatch(r'(?:target |animal |human )?cell',name,re.I):
        return 'cell'
    if re.search(r'\b(?:wall|lining|valve|epithelium|nucleus|plate|receptor)\b',name,re.I):
        return shape
    for pattern,native in ((r'\bred blood cells?\b','red_blood_cell'),(r'\bblood vessels?|capillar(?:y|ies)\b','blood_vessel'),
                           (r'\b(?:pill|tablet)s?\b','tablet'),(r'\bcapsules?\b','capsule'),
                           (r'\b(?:esophagus|oesophagus)\b','esophagus'),(r'\bstomach\b','stomach'),
                           (r'\b(?:small intestine|intestine)\b','intestine'),(r'\bvill(?:us|i)\b','villus'),
                           (r'\bliver\b','liver'),(r'\bkidneys?\b','kidney'),(r'\bheart\b','heart'),
                           (r'\blungs?\b','lung'),(r'\balveol(?:us|i)\b','alveolus'),(r'\bneurons?\b','neuron')):
        if re.search(pattern,name,re.I):
            return native
    return shape


@dataclass(frozen=True)
class Component:
    part: Part
    shape: str
    color: str
    pivot: tuple
    points: tuple
    links: tuple = ()
    geometry: tuple = ()
    electrical_role: str = ''


@dataclass(frozen=True)
class Action:
    beat: int
    part: str
    effect: str
    amount: tuple
    start: float
    end: float


def read_mechanism(data, beats, *, require_animation=True):
    entries, events = data["parts"], data["actions"]
    if (not isinstance(entries,list) or not isinstance(events,list)
            or not 1 <= len(entries) <= 24 or not (1 if require_animation else 0) <= len(events) <= 64):
        raise ValueError("Invalid mechanism size")
    components = {}
    for item in entries:
        name = _name(item["name"])
        shape = _biological_shape(name,_electrical_shape(name,item["shape"]))
        pivot = _pair(item["pivot"], 0, 100,f'{name}.pivot')
        points = tuple(_pair(point, 0, 100,f'{name}.points[{index}]') for index,point in enumerate(item["points"]))
        if (not name or name.casefold() in components or shape not in SHAPES or not 2 <= len(points) <= 48
                or (shape == "contour" and len(points) < 3) or len(set(points)) < 2):
            raise ValueError("Invalid mechanism component")
        if shape in ("solid","plate","gear","oval", *[s for s in ELECTRICAL_SHAPES if s != "wire"],
                     *[s for s in BIOLOGICAL_SHAPES if s not in ('blood_vessel','ureter','digestive_tube')]) and any(len(set(axis)) < 2 for axis in zip(*points)):
            raise ValueError(f"{name} ({shape}) has no width or height: {points}. Filled components need opposite corners with BOTH different x and different y, e.g. a thin horizontal base [[10,70],[90,74]]. Use pipe/path for a centreline")
        alias = re.escape(name) + ("" if name.endswith("s") else "s?")
        label = name[0].upper()+name[1:]
        part = Part(label, (label,), "detail", alias)
        links=item.get('links',[])
        links=tuple(tuple(link) for link in links) if links and all(isinstance(link,(tuple,list)) and len(link)==2 for link in links) else ()
        geometry=read_solids(item.get('geometry'),name,PALETTE) if shape=='solid' else ()
        electrical_role=item.get('electrical_role','')
        if electrical_role not in ('','source','load','conductor'):
            raise ValueError(f'{name}: unsupported electrical role')
        components[name.casefold()] = Component(part, shape, PALETTE[item["color"]], pivot, points,links,geometry,electrical_role)
    actions = []
    for item in events:
        beat, effect = item["beat"], item["effect"]
        name = _name(item["part"]).casefold()
        amount = _pair(item["amount"], -720, 720,f'{item["part"]} beat {beat} amount')
        start, end = _pair([item["start"], item["end"]], 0, 1,f'{item["part"]} beat {beat} timing')
        if start >= end:
            raise ValueError(f"{item['part']} on beat {beat} needs start < end; received {start}, {end}")
        if (type(beat) is not int or not 1 <= beat < beats or name not in components
                or effect not in EFFECTS):
            raise ValueError("Invalid mechanism action")
        if effect == "move" and max(map(abs, amount)) > 55:
            raise ValueError("Invalid travel distance")
        if effect == "expand" and any(not .25 <= value <= 2.5 for value in amount):
            raise ValueError("Invalid scale")
        if ((effect == "move" and amount == (0,0)) or (effect == "turn" and not amount[0])
                or (effect == "expand" and amount == (1,1))):
            continue
        if effect in ("flow","current") and components[name].shape not in ("pipe", "path", "wire",'blood_vessel','esophagus','intestine','neuron','ureter','digestive_tube'):
            raise ValueError(f"{components[name].part.label}: {effect} needs a wire, pipe or connected route; never apply current to a solid component")
        if effect == "current" and not -1. <= amount[0] <= 1.:
            raise ValueError("Current level must be between -1 and 1")
        if effect == "energize" and not 0. <= amount[0] <= 1.:
            raise ValueError("Invalid heat, light, or pressure level")
        if effect=='spin' and (not -4<=amount[0]<=4 or components[name].shape=='switch'):
            raise ValueError('Spin needs a rotating part and a speed from -4 to 4 revolutions per second')
        if effect=='charge' and (components[name].shape!='capacitor' or not 0<=amount[0]<=1):
            raise ValueError('Charge needs a capacitor and a normalized fraction between 0 and 1')
        if effect=='switch' and (components[name].shape!='switch' or amount[0] not in (0,1)):
            raise ValueError('Switch action needs a native switch and 0 (open) or 1 (closed)')
        if effect=='turn' and components[name].shape=='switch':
            raise ValueError('Use switch [0 or 1,0] to move the blade, not turn the fixed switch base')
        if effect=='dissolve' and (components[name].shape not in ('tablet','capsule') or not 0<=amount[0]<=1):
            raise ValueError('Dissolve needs a tablet/capsule and a fraction between 0 and 1')
        if effect=='pulse' and (components[name].shape not in BIOLOGICAL_SHAPES or not 0<=amount[0]<=4 or not 0<=amount[1]<=.25):
            raise ValueError('Biological pulse needs 0..4 cycles per second and 0..0.25 amplitude')
        actions.append(Action(beat, components[name].part.label, effect, amount, start, end))
    if require_animation and not actions:
        raise ValueError('The animation has no nonzero motion or changing state')
    if require_animation and all(action.effect in ("spin","current","energize","charge","pulse","dissolve","switch") and not action.amount[0] for action in actions):
        raise ValueError("The animation never moves or changes state")
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


def parse_mechanism_rows(data, beats, *, require_animation=True):
    # Read older saved layouts too, while generating strictly typed JSON from now on.
    if data.get("parts") and isinstance(data["parts"][0], dict):
        return read_mechanism({**data,'actions':data.get('actions',[])}, beats,require_animation=require_animation)
    def pair(text):
        return [float(value) for value in text.split(",")]

    parts = []
    for row in data["parts"]:
        name,shape,color,pivot,points = (value.strip() for value in row.split("|"))
        parts.append({"name":name,"shape":shape,"color":color,"pivot":pair(pivot),
                      "points":[pair(point) for point in points.split()]})
    actions = []
    for row in data.get("actions",[]):
        beat,part,effect,amount,timing = (value.strip() for value in row.split("|"))
        start,end = pair(timing)
        actions.append({"beat":int(beat),"part":part,"effect":effect,"amount":pair(amount),"start":start,"end":end})
    return read_mechanism({"parts":parts,"actions":actions},beats,require_animation=require_animation)


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
        elif action.effect == "flow" and 0. < p < 1.:
            flow = p if x >= 0 else -p
    return dx,dy,turn,sx,sy,heat,flow


def current_level(events, beat, fraction):
    """Persist signed current between beats, with an immediate open-contact stop."""
    level = 0.
    for action in events:
        if action.effect == "current" and (action.beat < beat or action.beat == beat and fraction >= action.start):
            target=action.amount[0]
            p=1. if action.beat<beat else min(1.,max(0.,(fraction-action.start)/(action.end-action.start)))
            level=0. if not target else level+(target-level)*(p*p*(3-2*p))
    return level


def biological_level(events,effect,beat,fraction):
    level=0.
    for action in events:
        if action.effect!=effect or action.beat>beat:
            continue
        p=1. if action.beat<beat else min(1.,max(0.,(fraction-action.start)/(action.end-action.start)))
        level+=(action.amount[0]-level)*(p*p*(3-2*p))
    return level


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
    if component.shape in ("contour","path","pipe","wire",'blood_vessel','ureter','digestive_tube'):
        return points
    if component.shape in ("solid","plate") or component.shape in (*ELECTRICAL_SHAPES,*BIOLOGICAL_SHAPES):
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
        spins=any(a.effect=='spin' and a.amount[0] for a in events)
        for action in events:
            for index in range(9):
                fraction = action.start+(action.end-action.start)*index/8
                outline,centre,_,_=_transform(component,events,action.beat,fraction)
                points.extend(outline)
                if spins:
                    radius=max(dist(centre,p) for p in outline)
                    points.extend((centre[0]+dx*radius,centre[1]+dy*radius) for dx,dy in ((-1,0),(1,0),(0,-1),(0,1)))
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
