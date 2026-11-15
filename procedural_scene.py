# SPDX-License-Identifier: MIT
"""Turn a bounded object description into an animated, labeled 3D stage."""

from dataclasses import dataclass, replace
from math import cos, sin
import re

import numpy as np

from cinematic_geometry import scale, spin, translate
from explainer_parts import Part


SHAPES = {
    "box": "beveled-box", "sphere": "sphere", "cylinder": "cylinder",
    "cone": "cone", "ring": "groove", "prism": "prism", "wave": "wave", "wave-double": "wave-double",
}
COLORS = {
    "steel": (.42,.52,.61,.74), "graphite": (.21,.25,.29,.40), "white": (.80,.83,.85,.22),
    "gold": (.94,.56,.16,.53), "red": (.79,.18,.14,.35), "blue": (.17,.54,.91,.32),
    "green": (.22,.70,.46,.25), "violet": (.62,.34,.82,.36), "cyan": (.15,.81,.83,.22),
}
POSES = ("front", "upright", "across", "tilted-left", "tilted-right", "across-up", "across-down")
MOTIONS = ("still", "spin", "lift", "pulse", "orbit", "slide", "sway", "flow", "rain")
RELATIONS = ("free", "on-top", "in-front", "on-left", "on-right")
DIRECTIONS = {"none":(0,0,0), "up":(0,1,0), "down":(0,-1,0), "left":(-1,0,0),
              "right":(1,0,0), "forward":(0,0,1), "back":(0,0,-1)}
MAX_OBJECTS = 12
_X_UP = np.array(((1,0,0,0),(0,0,1,0),(0,-1,0,0),(0,0,0,1)), dtype=float)
_Y_ACROSS = np.array(((0,0,1,0),(0,1,0,0),(-1,0,0,0),(0,0,0,1)), dtype=float)
_POSES = {"front":np.eye(4), "upright":_X_UP, "across":_Y_ACROSS,
          "tilted-left":spin(.42), "tilted-right":spin(-.42),
          "across-up":spin(.20) @ _Y_ACROSS,"across-down":spin(-.30) @ _Y_ACROSS}


@dataclass(frozen=True)
class StageObject:
    label: str
    shape: str
    color: str
    position: tuple
    size: tuple
    pose: str = "front"
    motion: str = "still"
    relation: str = "free"
    anchor: str = ""


@dataclass(frozen=True)
class StageAction:
    beat: int
    part: str
    travel: tuple
    turn: float
    start: float
    end: float


def read_actions(data, stage, scenes):
    entries = data.get("actions", [])
    if not isinstance(entries, list):
        return ()
    labels = {obj.label.casefold():obj.label for obj in stage}
    actions = []
    for item in entries[:24]:
        try:
            beat, part = item["beat"], labels[item["part"].strip().casefold()]
            direction = item["direction"]
            distance, turn, start, end = (item[field] for field in ("distance", "turn", "start", "end"))
            if (type(beat) is not int or not 0 <= beat < len(scenes) or direction not in DIRECTIONS
                    or any(type(value) not in (int, float) for value in (distance, turn, start, end))
                    or not 0 <= distance <= 1.8 or not -720 <= turn <= 720 or not 0 <= start < end <= 1):
                continue
            narration = scenes[beat]["narration"]
            down = bool(re.search(r"\b(?:downwards?|lower(?:s|ed|ing)? the)\b", narration, re.I))
            up = bool(re.search(r"\b(?:upwards?|lift(?:s|ed|ing)? (?:the|away)|rais(?:e|es|ed|ing) the)\b", narration, re.I))
            if direction in ("up", "down") and down != up:
                direction = "down" if down else "up"
            travel = tuple(component*distance for component in DIRECTIONS[direction])
            if not any(travel) and not turn:
                continue
            actions.append(StageAction(beat, part, travel, turn, start, end))
        except (AttributeError, KeyError, TypeError, ValueError):
            continue
    return tuple(actions)


def _vector(value, minimum, maximum):
    if (not isinstance(value, list) or len(value) != 3
            or any(type(item) not in (int, float) or not minimum <= item <= maximum for item in value)):
        raise ValueError("Invalid scene dimensions")
    return tuple(float(item) for item in value)


def _assemble(stage):
    by_label = {obj.label.casefold():obj for obj in stage}
    offsets = {"on-top":(1,1), "in-front":(2,1), "on-left":(0,-1), "on-right":(0,1)}
    resolved = {}

    def extent(obj):
        local = (.5,.5,.5) if obj.shape == "box" else (1.,1.,.5) if obj.shape in ("cylinder","cone") else (1.,1.,1.)
        return np.abs(_POSES[obj.pose][:3,:3]) @ (np.asarray(obj.size)*local)

    for obj in stage:
        chain, seen = [], set()
        cursor = obj
        while cursor.label not in resolved and cursor.label not in seen:
            seen.add(cursor.label)
            chain.append(cursor)
            parent = by_label.get(cursor.anchor.casefold())
            if cursor.relation == "free" or parent is None or parent.label in seen:
                resolved[cursor.label] = cursor
                chain.pop()
                break
            cursor = parent
        for child in reversed(chain):
            parent = resolved[by_label[child.anchor.casefold()].label]
            axis, direction = offsets[child.relation]
            a, b = extent(parent)[axis], extent(child)[axis]
            position = list(parent.position)
            position[axis] += direction*(a+b-.16*min(a,b))
            resolved[child.label] = replace(child, position=tuple(position))
    return tuple(resolved[obj.label] for obj in stage)


def read_stage(data):
    """Accept numbers and known enums only. A model response is never executed."""
    if not isinstance(data, dict) or not isinstance(data.get("objects"), list):
        raise ValueError("Missing 3D objects")
    stage = []
    seen = set()
    for entry in data["objects"][:MAX_OBJECTS]:
        try:
            name = entry["label"]
            if not isinstance(name, str):
                continue
            name = " ".join(re.sub(r"[^\w\s'’&/-]", "", name).split())[:32].strip()
            shape, color, pose, motion = (entry[key] for key in ("shape", "color", "pose", "motion"))
            if (not name or name.casefold() in seen or shape not in SHAPES or color not in COLORS
                    or pose not in POSES or motion not in MOTIONS):
                continue
            position = _vector(entry["position"], -2.5, 2.5)
            size = _vector(entry["size"], .035, 2.65)
            relation = entry.get("relation", "free")
            anchor = entry.get("anchor", "")
            if relation not in RELATIONS or not isinstance(anchor, str):
                relation, anchor = "free", ""
        except (KeyError, TypeError, ValueError):
            continue
        seen.add(name.casefold())
        stage.append(StageObject(name, shape, color, position, size, pose, motion, relation, anchor[:32].strip()))
    if len(stage) < 2:
        raise ValueError("At least two visible 3D objects are required")
    return _assemble(stage)


def stage_parts(stage):
    groups = {}
    for index, item in enumerate(stage):
        groups.setdefault(item.label, []).append(f"item-{index}")
    parts = []
    for label, targets in groups.items():
        alias = re.escape(label)
        if label[-1].isalpha() and not label.endswith("s"):
            alias += "s?"
        parts.append(Part(label, tuple(targets), "detail", alias))
    return tuple(parts)


def storyboard_stage(scenes):
    """Build a labeled concept scene when the object plan is unavailable."""
    points = tuple((x,y,0) for y in (1.44,.66,-.12,-.90) for x in (-.72,.72))
    shapes = ("ring", "sphere", "prism", "cylinder", "box", "cone", "sphere", "prism")
    colors = ("cyan", "gold", "blue", "violet", "green", "red", "steel", "white")
    return tuple(StageObject(scene["heading"][:31], shape, color, center, (.30,.30,.27), motion="pulse")
                 for scene, shape, color, center in zip(scenes[1:], shapes, colors, points))


def _motion(obj, t):
    phase = t * 1.45
    wave = sin(phase)
    if obj.motion == "spin":
        return spin(phase)
    if obj.motion == "lift":
        return translate(0, .36*wave, 0)
    if obj.motion == "pulse":
        size = 1 + .16*wave
        return scale(size, size, size)
    if obj.motion == "orbit":
        x, _, z = obj.position
        return translate(x*(cos(phase)-1) + z*sin(phase), 0, z*(cos(phase)-1) - x*sin(phase))
    if obj.motion == "slide":
        return translate(.53*wave, 0, 0)
    if obj.motion == "sway":
        return spin(.26*wave)
    if obj.motion == "flow":
        return translate(0, .75*((t*.58 + obj.position[0]) % 1), 0)
    if obj.motion == "rain":
        return translate(0, -.83*((t*.85 + obj.position[0]) % 1), 0)
    return np.eye(4)


class StageShot:
    subject = "generated"

    def __init__(self, stage, view, caption, offset=0, *, actions=(), beat=0, duration=1.):
        self.stage = stage
        self.view = view
        self.caption = caption
        self.offset = offset
        self.beat = beat
        self.duration = duration
        self.actions = {obj.label:tuple(action for action in actions if action.part == obj.label and action.beat <= beat)
                        for obj in stage}
        self.motion_labels = {action.part for action in actions}
        by_label = {obj.label.casefold():obj for obj in stage}
        self.parents = {}
        for obj in stage:
            parents, seen = [], {obj.label}
            current = obj
            while current.relation != "free":
                parent = by_label.get(current.anchor.casefold())
                if parent is None or parent.label in seen:
                    break
                parents.append(parent)
                seen.add(parent.label)
                current = parent
            self.parents[obj.label] = parents
        centers = np.array([obj.position for obj in stage])
        low, high = centers.min(axis=0), centers.max(axis=0)
        self.center = (low + high) / 2
        self.radius = max(1.10, float(np.max(high-low)) / 2 + .60 * max(max(obj.size) for obj in stage))
        self.floor = min(-1.25, min(obj.position[1]-obj.size[1] for obj in stage)-.14)

    def at(self, t, part=None):
        time = t + self.offset
        sweep = sin(t*.50)
        objects = []
        focus = self.center
        radius = self.radius
        transforms = {}
        for obj in self.stage:
            shift, turn = np.zeros(3), 0.
            for action in self.actions[obj.label]:
                elapsed = 1. if action.beat < self.beat else t/self.duration
                fraction = float(np.clip((elapsed-action.start)/(action.end-action.start), 0., 1.))
                progress = fraction*fraction*(3-2*fraction)
                shift += np.asarray(action.travel)*progress
                turn += action.turn*progress
            motion = np.eye(4) if obj.label in self.motion_labels else _motion(obj,time)
            position = np.asarray(obj.position)
            transforms[obj.label] = translate(*(position+shift)) @ spin(np.deg2rad(turn)) @ motion @ translate(*(-position))
        for index, obj in enumerate(self.stage):
            group = f"item-{index}"
            model = transforms[obj.label] @ translate(*obj.position) @ _POSES[obj.pose] @ scale(*obj.size)
            for parent in self.parents[obj.label]:
                model = transforms[parent.label] @ model
            objects.append((SHAPES[obj.shape], COLORS[obj.color], model, group))
            if self.view == "detail" and part and group in part.groups:
                focus = model[:3,3]
                radius = max(.93, max(obj.size)*.86, self.radius*.60)
        if self.view == "overhead":
            eye = focus + np.array((.70+.20*sweep, 2.8, 1.45))*radius
        else:
            distance = 4.32 if self.view == "wide" or not part else 3.82
            eye = focus + np.array((.76+.32*sweep, .62, distance-.14*sweep))*radius
        return objects, tuple(eye), np.asarray(focus)


CURATED_STAGES = {
    "prism": (
        StageObject("Incoming light", "cylinder", "white", (-1.16,.26,.14), (.035,.035,1.25), "across"),
        StageObject("Glass prism", "prism", "blue", (-.28,.25,.06), (.65,.83,.56)),
        StageObject("Red light", "cylinder", "red", (.87,.40,.10), (.035,.035,1.46), "across-up", "pulse"),
        StageObject("Green light", "cylinder", "green", (.87,.24,.14), (.035,.035,1.46), "across", "pulse"),
        StageObject("Violet light", "cylinder", "violet", (.87,.04,.18), (.035,.035,1.46), "across-down", "pulse"),
    ),
    "sound": (
        StageObject("Low note", "wave", "blue", (0,.58,0), (1.37,.58,.60), motion="pulse"),
        StageObject("Octave above", "wave-double", "gold", (0,-.45,0), (1.37,.56,.60), "front", "pulse"),
        StageObject("Lower reference", "cylinder", "steel", (0,.58,-.15), (.025,.025,2.9), "across"),
        StageObject("Upper reference", "cylinder", "steel", (0,-.45,-.15), (.025,.025,2.9), "across"),
    ),
    "water": (
        StageObject("Lake", "sphere", "blue", (-.49,-.61,.28), (1.16,.13,.63)),
        StageObject("Land", "sphere", "green", (.36,-.82,.03), (1.74,.20,.84)),
        StageObject("Mountain", "cone", "steel", (1.00,-.16,-.30), (.68,.72,1.28), "upright"),
        StageObject("Mountain", "cone", "white", (1.00,.32,-.30), (.17,.18,.32), "upright"),
        StageObject("Runoff", "sphere", "blue", (.46,-.59,.22), (.71,.068,.19)),
        *(StageObject("Cloud", "sphere", "white", (x,y,-.04), size, motion="slide") for x,y,size in (
            (.01,1.10,(.42,.25,.32)), (.34,1.21,(.49,.30,.34)), (.69,1.07,(.48,.23,.30)))),
        *(StageObject("Rain", "sphere", "cyan", (x,y,.19), (.042,.115,.042), motion="rain")
          for x,y in ((.11,.95),(.34,1.0),(.63,.89))),
        *(StageObject("Water vapor", "sphere", "cyan", (x,y,.26), (.055,.087,.055), motion="flow")
          for x,y in ((-.98,-.27),(-.73,-.20),(-.52,-.23))),
    ),
}
