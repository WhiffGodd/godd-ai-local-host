# SPDX-License-Identifier: MIT
"""The modeled subjects supported by the cinematic renderer."""

from dataclasses import asdict, dataclass
import re


VIEWS = {
    "bicycle": ("wide", "pedal-crank", "rear-hub", "chain-drive", "coasting"),
    "gears": ("wide", "drive-mesh", "output-mesh", "gear-ratio"),
    "pulley": ("wide", "pulley-wheel", "lifted-load", "rope-and-handle"),
    "moon": ("wide", "lit-moon", "earth-and-moon", "orbital-plane"),
    "piston": ("wide", "piston-travel", "connecting-rod", "crankshaft"),
    "turbine": ("wide", "rotor-blades", "hub-and-shaft", "tower-and-nacelle"),
    "hydraulics": ("wide", "input-piston", "output-piston", "fluid-pipe"),
    "bearing": ("wide", "inner-race", "rolling-balls", "outer-race"),
    "disc_brake": ("wide", "spinning-rotor", "caliper-and-pads", "braking"),
    "freewheel": ("wide", "cutaway", "engagement", "coasting"),
    "toaster": ("wide", "loading", "latch", "heating", "browning", "release", "pop-up"),
    **dict.fromkeys(("prism", "sound", "water", "generated", "mechanism"), ("wide", "detail", "overhead")),
}


@dataclass(frozen=True)
class Template:
    id: str
    name: str
    category: str
    diagram: str
    coverage: str


TEMPLATES = {template.id: template for template in (
    Template("bicycle-drivetrain", "Bicycle Drivetrain", "Mechanisms", "bicycle",
             "Bicycle pedals, chain, cranks, sprockets, rear wheel and coasting"),
    Template("gear-train", "Gear Train", "Mechanisms", "gears",
             "Meshing spur gears, changes in direction and gear ratios"),
    Template("pulley-system", "Pulley System", "Mechanisms", "pulley",
             "A single fixed pulley, tension, changing the direction of a pull and lifting a load"),
    Template("lunar-orbit", "Lunar Orbit", "Space", "moon",
             "The Moon orbiting Earth, its lit side, and lunar phases"),
    Template("piston-and-crank", "Piston and Crank", "Mechanisms", "piston",
             "A reciprocating piston, connecting rod, and rotating crankshaft in a cutaway"),
    Template("wind-turbine", "Wind Turbine", "Energy", "turbine",
             "A wind turbine rotor, pitched blades, tower, hub, and shaft inside the nacelle"),
    Template("hydraulic-lift", "Hydraulic Lift", "Mechanisms", "hydraulics",
             "A small input piston sending pressure through fluid to lift a load on a larger output piston"),
    Template("ball-bearing", "Ball Bearing", "Mechanisms", "bearing",
             "A ball bearing with an inner race, rolling balls, a cage, and a fixed outer race"),
    Template("disc-brake", "Disc Brake", "Mechanisms", "disc_brake",
             "A disc brake with a spinning rotor and caliper pads that clamp it and slow it down"),
    Template("freewheel-cutaway", "Bicycle Freewheel Cutaway", "Mechanisms", "freewheel",
             "A hub cover moves aside to show pawls engaging the ratchet under pedaling and clicking past the moving ratchet when coasting"),
    Template("pop-up-toaster", "Pop-up Toaster", "Mechanisms", "toaster",
             "Two slices of bread, the lever and carriage, a compressed spring, glowing heating wires, and the toast popping up"),
    Template("light-prism", "Light Through a Prism", "Science", "prism",
             "An incoming beam and the colors that leave a glass prism at different angles"),
    Template("sound-octave", "Sound and Octaves", "Science", "sound",
             "A low note and the waveform of the note one octave above it, at twice the frequency"),
    Template("water-cycle", "Water Cycle", "Nature", "water",
             "A lake, rising water vapor, clouds, falling rain, and land"),
)}

GENERATED_TEMPLATE = Template("generated", "AI-illustrated scenes", "Custom", "generated",
                              "Detailed images generated for each shot in the storyboard")
MECHANISM_TEMPLATE = Template("mechanism", "Animated cutaway", "Custom", "mechanism",
                              "A step-by-step diagram of the parts and how they work together")


def matching_subjects(prompt):
    if re.search(r"\b(?:freewheels?|freehubs?|(?:bicycle|bike)\b.*\bpawls?|bicycle ratchets?)\b", prompt, re.I):
        return [TEMPLATES["freewheel-cutaway"]]
    terms = {
        "bicycle-drivetrain": r"\b(?:bicycles?|bikes?|cycles?)\b.*\b(?:pedal\w*|cranks?|chain|chainrings?|sprockets?|coast\w*)\b|\b(?:pedal\w*|cranks?|chainrings?)\b.*\b(?:bicycles?|bikes?)\b|\b(?:freewheels?|bicycle drivetrains?)\b",
        "gear-train": r"\b(?:meshing gears?|gear trains?|gear ratios?|spur gears?|touching gears|gears? mesh)\b",
        "pulley-system": r"\bpulleys?\b",
        "lunar-orbit": r"\b(?:moon phases?|lunar phases?|lunar orbit|crescent moon)\b|\bmoon\b.*\b(?:phases?|orbit\w*|earth)\b",
        "piston-and-crank": r"\b(?:piston\b.*\bcrank\w*|crank\w*\b.*\bpiston|slider[- ]crank|reciprocating piston)s?\b",
        "wind-turbine": r"\b(?:wind turbines?|wind power rotor)\b",
        "hydraulic-lift": r"\b(?:hydraulic (?:lifts?|jacks?|press(?:es)?|pistons?)|pascal.s principle)\b",
        "ball-bearing": r"\b(?:ball bearings?|bearing races?)\b",
        "disc-brake": r"\b(?:dis[ck] brakes?|brake rotors?|brake calipers?)\b",
        "pop-up-toaster": r"\btoasters?\b(?![ -]+(?:ovens?|industr(?:y|ies)))",
        "light-prism": r"\b(?:prisms?|prismatic dispersion)\b",
        "sound-octave": r"\b(?:octaves?|octave frequency)\b",
        "water-cycle": r"\b(?:water cycle|hydrologic(?:al)? cycle|evaporation.*condensation)\b",
    }
    return [TEMPLATES[name] for name, pattern in terms.items()
            if re.search(pattern, prompt, re.IGNORECASE | re.DOTALL)]


def template_catalog():
    return [{**asdict(template),
             "poster": f"/cinematic/{template.id}.webp",
             "preview": f"/cinematic/{template.id}.webm"}
            for template in TEMPLATES.values()]
