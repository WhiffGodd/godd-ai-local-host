# SPDX-License-Identifier: MIT
"""Reviewed battery/switch/filament circuit with contact-dependent current."""
import re

import numpy as np
from PIL import ImageDraw

from cinematic_render import _font, _look_at, _perspective
from cinematic_geometry import scale, translate
from mechanism_animation import read_mechanism
from mechanism_3d import Mechanism3DShot
from electrical_detail import rounded_route


def matches_circuit(prompt):
    return (all(re.search(pattern,prompt,re.I) for pattern in
                (r"\bbatter(?:y|ies)\b",r"\b(?:bulb|lightbulb)s?\b",r"\bswitch\b"))
            and not re.search(r"\b(?:parallel|series[- ]parallel|AC|alternating|relay|motor|capacitor|transistor|rectifier|resistors?)\b",prompt,re.I))


def circuit_storyboard(max_seconds=25):
    steps = [
        ("Voltage without current", "The battery supplies voltage. An open switch breaks the circuit: no current flows."),
        ("Close the switch", "Close the contacts. Current heats the bulb's filament, producing light."),
        ("Inside the copper wire", "Blue electrons drift toward positive. Orange conventional current goes the opposite way."),
        ("Voltage drives current", "Voltage drives current. Energy transfers quickly; electron drift is much slower."),
        ("Open the switch", "Open the switch. Current stops, and the filament cools."),
    ]
    if max_seconds >= 60:
        explanations = [
            "Voltage is energy per unit charge. The gap prevents current despite voltage between the terminals.",
            "Resistance heats the filament. The remaining wire completes the return path to the battery.",
            "The particles are enlarged teaching markers. Electrons already exist throughout the copper; they do not start arriving from the battery.",
            "Current measures charge passing per second. The electrical signal travels through the circuit much faster than individual electrons drift.",
            "The battery still supplies voltage. Restoring the gap breaks the continuous path, cutting steady electrical power to the bulb.",
        ]
        steps = [(heading,text+" "+extra) for (heading,text),extra in zip(steps,explanations)]
    return {"template":"dc-circuit", "title":"How a Switch Lights a Bulb: Electricity Explained",
            "hook":"What makes this bulb light?", "hook_view":"wide",
            "description":"A continuous 3D cutaway of a battery, copper wiring, switch contacts and bulb filament. Blue represents electron drift; orange represents conventional current in the opposite direction. Particle size and speed are exaggerated for visibility. This is a qualitative circuit model, not an electrical simulation or wiring guide.",
            "hashtags":["#Electricity","#HowItWorks","#Science","#Shorts"],
            "scenes":[{"heading":heading,"view":"wide","narration":text,"caption":heading+"."}
                      for heading,text in steps]}


def circuit_mechanism(beats):
    if beats != 6:
        raise ValueError("The reviewed circuit needs its six narration beats")
    parts = [
        {"name":"Battery","shape":"battery","color":"dark","pivot":[21,58],"points":[[14,43],[28,74]]},
        {"name":"Positive wire","shape":"wire","color":"gold","pivot":[21,43],"points":[[21,43],[21,26],[43,26]]},
        {"name":"Switch base","shape":"switch","color":"white","pivot":[43,26],"points":[[43,22],[62,30]]},
        {"name":"Switch blade","shape":"contour","color":"gold","pivot":[43,26],"points":[[43,25],[62,25],[62,27],[43,27]]},
        {"name":"Bulb wire","shape":"wire","color":"gold","pivot":[62,26],"points":[[62,26],[90,26],[90,52],[86,52]]},
        {"name":"Bulb filament","shape":"bulb","color":"white","pivot":[77,52],"points":[[68,38],[86,66]]},
        {"name":"Return wire","shape":"wire","color":"gold","pivot":[68,52],"points":[[68,52],[57,52],[57,80],[21,80],[21,74]]},
    ]
    actions = [
        {"beat":1,"part":"Switch blade","effect":"turn","amount":[-36,0],"start":0.,"end":.01},
        {"beat":2,"part":"Switch blade","effect":"turn","amount":[36,0],"start":.08,"end":.48},
        {"beat":2,"part":"Bulb filament","effect":"energize","amount":[1,0],"start":.48,"end":.70},
        {"beat":3,"part":"Bulb filament","effect":"energize","amount":[1,0],"start":0.,"end":.1},
        {"beat":5,"part":"Switch blade","effect":"turn","amount":[-36,0],"start":.15,"end":.55},
        {"beat":5,"part":"Bulb filament","effect":"energize","amount":[0,0],"start":.15,"end":.48},
    ]
    # These are educational current events. The shot derives exact contact state
    # from blade rotation so markers cannot run through an open switch.
    for name in ("Positive wire","Bulb wire","Return wire"):
        for beat,level,start in ((2,1,.48),(4,1,0.),(5,0,.15)):
            actions.append({"beat":beat,"part":name,"effect":"current","amount":[level,0],"start":start,"end":min(1.,start+.01)})
    return read_mechanism({"parts":parts,"actions":actions},beats)


def circuit_state(beat,fraction):
    if beat <= 1:
        return -36.,False
    if beat == 2:
        p = min(1.,max(0.,(fraction-.08)/.40))
        return -36*(1-p*p*(3-2*p)),fraction >= .48
    if beat < 5:
        return 0.,True
    p = min(1.,max(0.,(fraction-.15)/.40))
    return -36*p*p*(3-2*p),fraction <= .15


class CircuitShot(Mechanism3DShot):
    """One fixed camera, with electron and current markers sharing a closed path."""
    subject = "dc-circuit"
    # Listed from the negative terminal, through load and switch, to positive.
    route = ((21,74),(21,80),(57,80),(57,52),(68,52),(73.58,52),
             (73.58,48.64),(80.42,48.64),(80.42,52),(86,52),
             (90,52),(90,26),(62,26),(43,26),(21,26),(21,43))

    def at(self,time,part=None):
        objects,eye,focus = super().at(time,part)
        fraction = min(1.,max(0.,time/max(self.duration-1/30,.01)))
        angle,closed = circuit_state(self.beat,fraction)
        from cinematic_geometry import spin
        pivot = self.model.world((43,26))
        objects = [(n,m,translate(*pivot)@spin(np.deg2rad(-angle))@translate(*(-pivot)) if g=="Switch blade" else mat,g)
                   for n,m,mat,g in objects]
        # Replace generic per-wire markers with a single continuous complete route.
        objects = [item for item in objects if item[0] != "sphere"]
        if closed:
            points = np.array([self.model.world(point,.09) for point in rounded_route(self.route)])
            lengths = np.linalg.norm(np.diff(points,axis=0),axis=1)
            total = lengths.sum()
            for direction,color,lane in ((1,(.12,.55,1.,7.),.025),(-1,(1.,.34,.07,7.),-.025)):
                for index in range(30):
                    remaining = ((direction*(self.offset+time)*.07+index/30)%1)*total
                    for a,b,length in zip(points,points[1:],lengths):
                        if length and remaining <= length:
                            point = a+(b-a)*remaining/length
                            point[0] += lane
                            objects.append(("sphere",color,translate(*point)@scale(.023,.023,.023),""))
                            break
                        remaining -= length
        self.camera = eye,focus
        return objects,eye,focus

    def overlay(self,frame,time):
        draw = ImageDraw.Draw(frame)
        width,height = self.size
        font = _font(round(width*.032))
        small = _font(round(width*.024))
        fraction = min(1.,max(0.,time/max(self.duration-1/30,.01)))
        _,closed = circuit_state(self.beat,fraction)
        draw.text((width*.07,height*.105),"A COMPLETE ELECTRICAL CIRCUIT",font=font,fill="#edf3e9")
        draw.text((width*.07,height*.14),"CONTACTS CLOSED  /  CURRENT ON" if closed else "CONTACTS OPEN  /  CURRENT ZERO",font=small,fill="#82d393" if closed else "#eab15b")
        draw.text((width*.07,height*.18),"BLUE: ELECTRON DRIFT  -  TO  +",font=small,fill="#55aafe")
        draw.text((width*.07,height*.204),"ORANGE: CONVENTIONAL CURRENT  +  TO  -",font=small,fill="#fa9c55")
        eye,focus = self.camera
        projection = _perspective(width/height,.78)@_look_at(eye,focus)
        def label(text,point,shift=(0,0),color="#c7d6e2"):
            p = projection@np.append(self.model.world(point,.18),1.)
            x,y = (p[:2]/p[3]*np.array((1,-1))+1)*np.array((width,height))/2
            x,y = x+shift[0]*width,y+shift[1]*height
            bounds = draw.textbbox((0,0),text,font=small)
            tw = bounds[2]-bounds[0]
            x = min(width-tw-12,max(12,x-tw/2))
            draw.rounded_rectangle((x-5,y-3,x+tw+5,y+width*.031),radius=4,fill="#101b2a")
            draw.text((x,y),text,font=small,fill=color)
        label("BATTERY",(21,58),(-.05,0))
        label("+",(21,43),(-.04,-.012),"#fa9c55")
        label("-",(21,74),(-.04,-.008),"#55aafe")
        label("SWITCH",(52,26),(0,-.038))
        label("FILAMENT",(77,48),(0,-.052))
        label("COPPER WIRE",(57,80),(.07,.013))
        draw.text((width*.07,height*.91),"QUALITATIVE CUTAWAY - PARTICLES ENLARGED",font=small,fill="#8ba6ba")
