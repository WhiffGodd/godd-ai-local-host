# SPDX-License-Identifier: MIT
"""Reviewed sliding-latch narration and a connected retract-and-return cycle."""

import re

from mechanism_animation import read_mechanism


def matches_latch(prompt):
    return bool(re.search(r"\b(?:spring[- ]loaded (?:sliding )?latch|sliding (?:latch|bolt))\b",prompt,re.I))


def latch_storyboard():
    steps = [
        ("The bolt starts extended","wide",
         "The sliding bolt starts inside the strike block. The fixed housing keeps it aligned. Behind the bolt, a return spring sits between the bolt and the left housing wall."),
        ("Pull the handle partway","detail",
         "Pull the handle to the left. Because the handle is attached to the bolt, both slide together. The return spring shortens as the bolt moves toward the back wall."),
        ("Retract the bolt fully","detail",
         "Keep pulling until the bolt clears the strike. The spring is now more compressed and stores elastic energy. Holding the handle keeps the bolt retracted."),
        ("Release and return halfway","detail",
         "Let go of the handle. The spring expands and pushes the bolt to the right. The handle travels with it, while the housing guides the returning assembly."),
        ("The latch returns to its start","wide",
         "The bolt enters the strike again and reaches its extended position. The housing and strike stay fixed throughout. Your pull retracts the bolt; the spring supplies its return motion."),
    ]
    return {"template":"spring-loaded-latch","title":"How a Spring-Loaded Sliding Latch Returns",
            "hook":"Why does this sliding latch spring back?","hook_view":"wide",
            "description":"Follow a sliding bolt and handle through partial retraction, full retraction, release, and spring-driven return in a connected 3D cutaway.",
            "hashtags":["#Mechanisms","#Engineering","#HowItWorks","#Shorts"],
            "scenes":[{"heading":heading,"view":view,"narration":text,"caption":heading+"."}
                      for heading,view,text in steps]}


def latch_mechanism(beats):
    if beats<5:
        raise ValueError("The latch cycle needs its explanation stages")
    parts = [
        {"name":"Housing","shape":"contour","color":"steel","pivot":[18,52],
         "points":[[18,38],[75,38],[75,43],[25,43],[25,62],[75,62],[75,67],[18,67]]},
        {"name":"Strike block","shape":"contour","color":"steel","pivot":[94,52],
         "points":[[89,42],[98,42],[98,65],[89,65],[89,60],[95,60],[95,46],[89,46]]},
        {"name":"Sliding bolt","shape":"contour","color":"white","pivot":[48,52],
         "points":[[48,47],[90,47],[94,50],[94,55],[90,58],[48,58]]},
        {"name":"Pull handle","shape":"contour","color":"blue","pivot":[55,59],
         "points":[[52,57],[58,57],[58,77],[64,77],[64,82],[48,82],[48,77],[52,77]]},
        {"name":"Return spring","shape":"spring","color":"gold","pivot":[25,52],
         "points":[[25,52],[48,52]]},
    ]
    # Body stages begin with the extended latch, then visit half/full retract
    # and half/full return. The shared easing keeps the bolt, handle and spring
    # endpoint coincident at every intermediate frame, not just at stage ends.
    waypoints = {1:0.,round(1+(beats-2)/4):.5,round(1+(beats-2)/2):1.,
                 round(1+3*(beats-2)/4):.5,beats-1:0.}
    states,current = [0.],0.
    for beat in range(1,beats):
        current = waypoints.get(beat,current)
        states.append(current)
    actions = []
    for beat,(before,after) in enumerate(zip(states,states[1:]),1):
        if abs(after-before)<1e-9:
            continue
        travel = -12*(after-before)
        for name in ("Sliding bolt","Pull handle"):
            actions.append({"beat":beat,"part":name,"effect":"move","amount":[travel,0],"start":.08,"end":.85})
        ratio = (23-12*after)/(23-12*before)
        actions.append({"beat":beat,"part":"Return spring","effect":"expand","amount":[ratio,1],"start":.08,"end":.85})
    return read_mechanism({"parts":parts,"actions":actions},beats)
