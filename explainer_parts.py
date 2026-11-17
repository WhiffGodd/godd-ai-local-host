# SPDX-License-Identifier: MIT
"""Part names and narration aliases for the modeled explainer subjects."""

from dataclasses import dataclass
from functools import lru_cache
import re


@dataclass(frozen=True)
class Part:
    label: str
    groups: tuple[str, ...]
    view: str
    aliases: str
    mesh_edge: float = 0.


PARTS = {
    "bicycle": (
        Part("Chainring", ("chainring",), "chain-drive", r"chainrings?|front sprockets?|front (?:gear|cog)"),
        Part("Rear sprocket", ("cog",), "rear-hub", r"rear (?:sprockets?|cogs?|gears?)|cogs?"),
        Part("Rear hub", ("rear-hub",), "rear-hub", r"(?:rear )?hubs?"),
        Part("Crank arm", ("crank",), "pedal-crank", r"crank(?: arms?)?"),
        Part("Pedals", ("pedal",), "pedal-crank", r"pedals?"),
        Part("Chain", ("chain",), "chain-drive", r"chain(?: links?)?"),
        Part("Rear wheel", ("rear-wheel",), "coasting", r"(?:rear|back) wheels?"),
    ),
    "gears": (
        Part("Input gear", ("drive",), "drive-mesh", r"(?:input|drive|driving|first) gears?"),
        Part("Idler gear", ("idler",), "drive-mesh", r"idler(?: gears?)?|middle gears?"),
        Part("Output gear", ("output",), "output-mesh", r"(?:output|driven|last) gears?"),
        Part("Gear teeth", ("drive", "idler", "output"), "gear-ratio", r"(?:gear )?teeth|tooth", mesh_edge=.86),
    ),
    "pulley": (
        Part("Pulley wheel", ("wheel",), "pulley-wheel", r"pulley(?: wheels?)?|sheaves?|wheels?"),
        Part("Rope", ("rope",), "rope-and-handle", r"ropes?|cords?"),
        Part("Load", ("load",), "lifted-load", r"loads?|weights?"),
        Part("Pull handle", ("handle",), "rope-and-handle", r"handles?|free end"),
    ),
    "moon": (
        Part("Moon", ("moon",), "lit-moon", r"moon(?:'s)?"),
        Part("Earth", ("earth",), "earth-and-moon", r"earth(?:'s)?"),
    ),
    "piston": (
        Part("Connecting rod", ("rod",), "connecting-rod", r"connecting rods?|conrods?"),
        Part("Crankshaft", ("crank",), "crankshaft", r"crankshafts?|crank(?: pins?)?"),
        Part("Piston", ("piston",), "piston-travel", r"pistons?"),
        Part("Cylinder", ("cylinder",), "piston-travel", r"cylinders?"),
    ),
    "turbine": (
        Part("Rotor blades", ("blades",), "rotor-blades", r"(?:rotor )?blades?"),
        Part("Rotor assembly", ("blades", "hub"), "rotor-blades", r"rotors?"),
        Part("Hub", ("hub",), "hub-and-shaft", r"hubs?"),
        Part("Drive shaft", ("shaft",), "hub-and-shaft", r"(?:drive )?shafts?"),
        Part("Nacelle", ("nacelle",), "tower-and-nacelle", r"nacelles?|housings?"),
        Part("Tower", ("tower",), "tower-and-nacelle", r"towers?"),
    ),
    "hydraulics": (
        Part("Input piston", ("input",), "input-piston", r"(?:input|small(?:er)?) (?:pistons?|cylinders?)"),
        Part("Output piston", ("output",), "output-piston", r"(?:output|larger?|large) (?:pistons?|cylinders?)"),
        Part("Hydraulic fluid", ("fluid",), "fluid-pipe", r"(?:hydraulic )?fluid|liquid|oil"),
        Part("Load", ("load",), "output-piston", r"loads?|weights?"),
    ),
    "bearing": (
        Part("Inner race", ("inner",), "inner-race", r"inner (?:race|ring)"),
        Part("Outer race", ("outer",), "outer-race", r"outer (?:race|ring)"),
        Part("Rolling balls", ("balls",), "rolling-balls", r"rolling (?:balls?|elements?)|(?:steel )?balls?"),
        Part("Bearing cage", ("cage",), "rolling-balls", r"(?:bearing )?cage|retainer"),
    ),
    "disc_brake": (
        Part("Brake pads", ("pad-1", "pad1"), "caliper-and-pads", r"(?:brake )?pads?"),
        Part("Rotor", ("rotor",), "spinning-rotor", r"(?:brake )?rotors?|brake dis[ck]s?"),
        Part("Caliper", ("caliper",), "caliper-and-pads", r"(?:brake )?calipers?"),
    ),
    "freewheel": (
        Part("Pawls", ("pawl0", "pawl1", "pawl2"), "engagement", r"(?:spring-loaded )?pawls?"),
        Part("Ratchet ring", ("ratchet",), "cutaway", r"ratchet(?: rings?| teeth)?|teeth"),
        Part("Sprocket", ("sprocket",), "wide", r"sprockets?|rear cogs?"),
        Part("Hub shell", ("hub",), "cutaway", r"(?:hub|outer) shells?|wheel hubs?"),
        Part("Driver", ("driver",), "cutaway", r"(?:freewheel )?drivers?|inner carrier"),
    ),
    "toaster": (
        Part("Heating wires", ("heater",), "heating", r"heating (?:wires?|elements?|coils?)|resistance wires?"),
        Part("Return spring", ("spring",), "latch", r"(?:return )?spring"),
        Part("Carriage", ("carriage",), "latch", r"carriage|bread tray"),
        Part("Latch", ("latch",), "release", r"latch|catch"),
        Part("Lever", ("lever",), "loading", r"lever|handle"),
        Part("Bread", ("bread",), "loading", r"slices (?:of bread|of toast)|bread|toast"),
    ),
}


@lru_cache(maxsize=128)
def _part_pattern(parts):
    named = (f"(?P<p{i}>{part.aliases})" for i, part in enumerate(parts))
    return re.compile(r"\b(?:" + "|".join(named) + r")\b", re.IGNORECASE)


def part_mentions(subject, narration, custom_parts=()):
    parts = custom_parts or PARTS.get(subject, ())
    if not parts:
        return []
    return [(match.start(), parts[int(match.lastgroup[1:])])
            for match in _part_pattern(parts).finditer(narration)]
