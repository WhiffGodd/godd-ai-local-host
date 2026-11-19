# SPDX-License-Identifier: MIT
"""A visible rolling bearing with raceways, a pocketed cage and no-slip motion."""

from math import cos, pi, sin, sqrt, tau
import re

import numpy as np


BALL_COUNT = 10
PITCH_RADIUS = .78
BALL_RADIUS = .18
CENTER_Y = .16
INNER_SPEED = 1.35


def bearing_angles(time):
    """Absolute angles for a fixed outer race and zero contact angle.

    The cage carries the centres. Each ball also spins about its own centre.
    Both contact velocities satisfy rolling without slip in this ideal model.
    """
    inner = INNER_SPEED*time
    cage = inner*(PITCH_RADIUS-BALL_RADIUS)/(2*PITCH_RADIUS)
    ball = -cage*PITCH_RADIUS/BALL_RADIUS
    return inner, cage, ball


def bearing_transforms(time, separation=0., opening=0.):
    from cinematic_geometry import spin, translate
    inner, cage, ball = bearing_angles(time)
    pivot = translate(0,CENTER_Y,0)
    unpivot = translate(0,-CENTER_Y,0)
    transforms = {
        "inner": translate(0,0,-.55*separation) @ pivot @ spin(inner) @ unpivot,
        "outer": np.eye(4),
        "cage": translate(0,0,.78*separation) @ pivot @ spin(cage) @ unpivot,
        "outer-window": translate(3.*opening,.8*opening,.75*opening),
    }
    for index in range(BALL_COUNT):
        phase = tau*index/BALL_COUNT+cage
        transforms[f"ball{index}"] = (translate(PITCH_RADIUS*cos(phase),
            CENTER_Y+PITCH_RADIUS*sin(phase),.25*separation) @ spin(ball))
    return transforms


def _lathe(profile, start=0., sweep=tau):
    """Revolve a closed radius/depth profile, including real cutaway end faces."""
    vertices = []
    sections = max(12,round(144*sweep/tau))
    edges = list(zip(profile,profile[1:]+profile[:1]))
    for (r0,z0),(r1,z1) in edges:
        normal = np.array((z1-z0,-(r1-r0)))
        normal /= np.linalg.norm(normal)
        for index in range(sections):
            for u,v in ((0,0),(1,0),(1,1),(0,0),(1,1),(0,1)):
                angle = start+sweep*(index+u)/sections
                radius,z = (r0,z0) if not v else (r1,z1)
                c,s = cos(angle),sin(angle)
                vertices.append((radius*c,radius*s,z,normal[0]*c,normal[0]*s,normal[1]))
    if sweep < tau-.001:
        # Each race profile is radial-monotone, so a radial triangle strip
        # closes the two exposed ends without filling the centre bore.
        low,high = min(z for _,z in profile),max(z for _,z in profile)
        for angle,sign in ((start,-1),(start+sweep,1)):
            c,s = cos(angle),sin(angle)
            for index in range(48):
                z0 = low+(high-low)*index/48
                z1 = low+(high-low)*(index+1)/48
                def radii(z):
                    hits = []
                    for (ra,za),(rb,zb) in edges:
                        if abs(zb-za)>1e-8 and min(za,zb)-1e-8<=z<=max(za,zb)+1e-8:
                            hits.append(ra+(rb-ra)*(z-za)/(zb-za))
                    return min(hits),max(hits)
                a,b = radii(z0),radii(z1)
                for r,z in ((a[0],z0),(a[1],z0),(b[1],z1),
                            (a[0],z0),(b[1],z1),(b[0],z1)):
                    vertices.append((r*c,r*s,z,-sign*s,sign*c,0.))
    return vertices


def bearing_mesh(name):
    if name == "bearing-ball":
        from cinematic_geometry import mesh
        return mesh("sphere")
    groove = [(-.16+.32*index/32) for index in range(33)]
    if name == "bearing-inner":
        profile = [(.34,-.26),(.65,-.26),(.69,-.20)]
        profile += [(PITCH_RADIUS-sqrt(.186**2-z*z),z) for z in groove]
        profile += [(.69,.20),(.65,.26),(.34,.26)]
        return _lathe(profile)
    if name in ("bearing-outer","bearing-outer-cutaway","bearing-outer-window"):
        profile = [(.905,-.26),(1.15,-.26),(1.18,-.23),(1.18,.23),(1.15,.26),(.905,.26),(.87,.19)]
        profile += [(PITCH_RADIUS+sqrt(.186**2-z*z),z) for z in reversed(groove)]
        profile += [(.87,-.19)]
        if name.endswith("cutaway"):
            return _lathe(profile,pi/2,3*pi/2)
        if name.endswith("window"):
            return _lathe(profile,0.,pi/2)
        return _lathe(profile)
    raise ValueError("Unknown bearing mesh")


def bearing_geometry():
    from cinematic_geometry import CHROME, GOLD, STEEL, Subject, scale, translate
    subject = Subject()
    subject.place("beveled-box",STEEL,(0,-1.14,-.28),(2.75,.18,1.36))
    for x in (-.91,.91):
        subject.place("beveled-box",STEEL,(x,-.81,-.24),(.24,.53,.60))
    subject.add("bearing-outer-cutaway",STEEL,translate(0,CENTER_Y,0),"outer")
    subject.add("bearing-outer-window",STEEL,translate(0,CENTER_Y,0),"outer-window")
    subject.add("bearing-inner",CHROME,translate(0,CENTER_Y,0),"inner")
    subject.place("cylinder",STEEL,(0,CENTER_Y,-.32),(.335,.335,1.02),"inner")
    # Witness marks make rotation visible on otherwise symmetric metal surfaces.
    for index in range(4):
        angle = tau*index/4
        subject.place("beveled-box",(.10,.46,.68,.38),
            (.49*cos(angle),CENTER_Y+.49*sin(angle),.269),(.19,.046,.013),"inner",angle)
    for index in range(12):
        angle = tau*index/12
        group = "outer-window" if .001<angle<pi/2-.001 else "outer"
        subject.place("recessed-bolt",CHROME,
            (1.095*cos(angle),CENTER_Y+1.095*sin(angle),.272),(.037,.037,.034),group)
    for index in range(BALL_COUNT):
        angle = tau*index/BALL_COUNT
        x,y = PITCH_RADIUS*cos(angle),CENTER_Y+PITCH_RADIUS*sin(angle)
        # Balls start at their own origin so spinning never moves their centres.
        subject.add("bearing-ball",CHROME,scale(BALL_RADIUS,BALL_RADIUS,BALL_RADIUS),f"ball{index}")
        for z in (-.13,.13):
            subject.place("ring",GOLD,(x,y,z),(.203,.203,.045),"cage")
        midway = angle+pi/BALL_COUNT
        mx,my = PITCH_RADIUS*cos(midway),CENTER_Y+PITCH_RADIUS*sin(midway)
        subject.place("recessed-bolt",GOLD,(mx,my,.163),(.039,.039,.032),"cage")
        subject.pipe((mx,my,-.13),(mx,my,.13),.031,GOLD,"cage")
        # Two narrow straps join neighbouring pockets into one retainer.
        for z in (-.13,.13):
            left = angle+.21
            right = angle+tau/BALL_COUNT-.21
            subject.pipe((PITCH_RADIUS*cos(left),CENTER_Y+PITCH_RADIUS*sin(left),z),
                         (PITCH_RADIUS*cos(right),CENTER_Y+PITCH_RADIUS*sin(right),z),.028,GOLD,"cage")
    return subject


def _inspection(view):
    return (.75 if view == "exploded" else 0.,
            1. if view in ("cutaway","rolling-balls","cage") else 0.)


def _blend(elapsed):
    value = min(1.,max(0.,elapsed/.8))
    return value**3*(10+value*(-15+6*value))


def inspection_pose(view,previous_view=None,elapsed=1.):
    target = np.asarray(_inspection(view))
    if previous_view:
        old = np.asarray(_inspection(previous_view))
        target = old+(target-old)*_blend(elapsed)
    return tuple(target)


def bearing_shot(parts, view, time, progress, part=None, previous_view=None, elapsed=1.):
    # The exploded view is deliberately an inspection state. All operating
    # views keep the balls in the raceways and the cage centred on them.
    separation,opening = inspection_pose(view,previous_view,elapsed)
    amount = _blend(elapsed)
    transforms = bearing_transforms(time,separation,opening)
    objects = []
    for name,material,model,group in parts:
        if group == "outer-window" and opening>=.999:
            continue
        transform = transforms.get(group)
        objects.append((name,material,model if transform is None else transform@model,
                        "balls" if group.startswith("ball") else "outer" if group == "outer-window" else group))
    # Each close-up retains enough neighbouring parts to show their connection.
    cameras = {
        "wide": ((0,.12,0),(.65,.75,5.50)),
        "inner-race": ((0,.17,0),(.70,.70,4.65)),
        "outer-race": ((.05,.19,0),(.95,.85,4.90)),
        "rolling-balls": ((.38,.49,.03),(.50,.93,4.20)),
        "cutaway": ((.10,.22,0),(1.35,1.10,5.15)),
        "cage": ((.15,.25,.04),(.48,.60,4.65)),
        "exploded": ((0,.13,.05),(3.20,1.50,5.80)),
    }
    focus,eye = cameras[view]
    if previous_view:
        old_focus,old_eye = cameras[previous_view]
        focus = np.asarray(old_focus)+(np.asarray(focus)-old_focus)*amount
        eye = np.asarray(old_eye)+(np.asarray(eye)-old_eye)*amount
    return objects,eye,np.asarray(focus)


def spacing_storyboard(prompt, long_video=False):
    """Use a reviewed operating sequence for the model's ball-spacing lesson.

    Other bearing questions retain the AI planner. This sequence covers the
    demonstrated parts and motions, without inventing failure demonstrations.
    """
    if not re.search(r"\b(?:cages?|retainers?|spacing|spaced|bunch\w*|crash\w*|collid\w*)\b",prompt,re.I):
        return None
    if re.search(r"\b(?:fail\w*|broken|damag\w*|wear|lubric\w*|grease|ceramic|plastic|temperature|manufactur\w*)\b",prompt,re.I):
        return None
    hook = "Why don't these balls crash together?"
    requested = re.search(r'open with\s*["“]([^"”]+)["”]',prompt,re.I)
    if requested and 4<=len(requested[1].split())<=16 and len(requested[1])<=100:
        hook = requested[1]
    steps = [
        ("A pocket for each ball","exploded",
         "A cage keeps each ball in its own pocket. With the parts separated, you can see the two grooved rings, the steel balls, and the cage."),
        ("The shaft drives the inner race","inner-race",
         "Once assembled, the shaft turns the inner ring. The outer ring stays fixed in its housing, giving the balls a stationary track to roll against."),
        ("Each ball has two motions","rolling-balls",
         "Each ball has two motions. Its centre travels around the bearing, while the ball spins about its own centre. The orange marks make that spin visible."),
        ("The cage maintains the gaps","cage",
         "Watch the cage move with the ball centres. Its pockets maintain the gaps between neighbouring balls. The cage rotates more slowly than the inner ring."),
        ("The raceways guide rolling contact","cutaway",
         "The curved raceways guide the balls between the rings. Rolling contact carries the load while allowing the inner ring to turn with relatively little friction."),
        ("The complete working bearing","wide",
         "Put it together: the rings guide, the balls roll, and the cage maintains spacing. These connected motions keep the balls separated as the shaft turns."),
    ]
    if long_video:
        steps[4:4] = [
            ("The retainer follows the balls","cage",
             "Notice how a cage pocket follows the same ball centre all the way around. It does not repeatedly overtake the ball. The bearing has several different motions happening at the same time."),
            ("The contact surfaces work together","rolling-balls",
             "Look closely at the ball between the two races. Its own spin combines with the movement of its centre, allowing its surfaces to roll against both tracks. The marks help you follow one ball."),
        ]
    return {"template":"ball-bearing","title":"How a Bearing Cage Keeps the Balls Spaced",
            "hook":hook,"hook_view":"wide",
            "description":"See the inner race turn, each ball spin and travel, and the cage keep the balls spaced. Cutaway and exploded views reveal how the parts work together. Orange marks make rotation visible.",
            "hashtags":["#BallBearing","#Engineering","#HowItWorks","#Shorts"],
            "scenes":[{"heading":heading,"view":view,"narration":narration,
                       "caption":heading+"."} for heading,view,narration in steps]}
