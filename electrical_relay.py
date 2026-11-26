# SPDX-License-Identifier: MIT
"""Reviewed, electrically isolated DC relay with a connected return spring."""
from math import atan2, cos, radians, sin
import re

import numpy as np
from PIL import ImageDraw

from cinematic_geometry import scale, spin, translate
from cinematic_render import _font, _look_at, _perspective
from mechanism_3d import Mechanism3DShot
from mechanism_animation import motion_state, read_mechanism


def matches_relay(prompt):
    return bool(re.search(r'\b(?:DC |electromagnetic |electric(?:al)? |low[- ]voltage )?relay\b',prompt,re.I)
                and not re.search(r'\b(?:solid[- ]state|latching|time[- ]delay|alternating|AC|transistor|motor|normally closed|changeover|double[- ]pole)\b',prompt,re.I))


def relay_storyboard(max_seconds=60):
    steps = [
        ('Two separate circuits','The coil circuit and lamp circuit are electrically isolated. With both contacts open, neither carries current.'),
        ('Power the electromagnet','Close the control switch. Current through the copper winding magnetizes the iron core. The coil stays fixed.'),
        ('Pull the armature','The core attracts the pivoted steel armature. As it turns toward the core, the attached return spring stretches.'),
        ('Close the load contacts','The armature meets the load contact. Current now flows through the separate lamp circuit, heating its filament.'),
        ('Release and return','Open the control switch. The magnetic pull falls. The spring returns the armature, opening the load contacts and switching the lamp off.'),
    ]
    if max_seconds==25:
        steps = [
            ('Two separate circuits','The coil and lamp have separate circuits. Both start open.'),
            ('Power the electromagnet','Close the control switch. Coil current magnetizes the iron core.'),
            ('Pull the armature','Magnetic attraction turns the armature, stretching its return spring.'),
            ('Close the load contacts','The load contacts meet. Current lights the lamp.'),
            ('Release and return','Open the control switch. The spring returns the armature, disconnecting the lamp.'),
        ]
    else:
        extras = ['The coil operates the switch magnetically.', 'This creates an electromagnet inside the relay.',
                  'The pivot stays in its fixed position.', 'The two power sources remain electrically isolated.',
                  'The contacts physically separate during the return.']
        steps = [(h,n+' '+extra) for (h,n),extra in zip(steps,extras)]
    return {'template':'dc-relay','title':'How a Relay Switches a Separate Circuit',
            'hook':'How can a magnet operate a switch?','hook_view':'wide',
            'description':'A DC electromagnetic relay in continuous cutaway: control switch, copper coil and iron core, pivoted armature, return spring, isolated load contacts and lamp. Blue markers indicate electron drift. The magnetic-field lines and particle speed are qualitative teaching overlays.',
            'hashtags':['#Relay','#Electricity','#Engineering','#Shorts'],
            'scenes':[{'heading':h,'view':'wide','narration':n,'caption':h+'.'} for h,n in steps]}


def relay_mechanism(beats):
    if beats!=6:
        raise ValueError('The relay needs six narration beats')
    parts=[]
    def part(name,shape,points,color='steel',pivot=None):
        parts.append(dict(name=name,shape=shape,color=color,points=points,pivot=pivot or points[0]))
    part('Control battery','battery',[[8,65],[16,88]],'dark')
    part('Control switch','switch',[[8,44],[28,52]],'white')
    part('Control blade','contour',[[8,47],[28,47],[28,49],[8,49]],'gold',[8,48])
    part('Control feed','wire',[[12,65],[4,65],[4,48],[8,48]],'gold')
    part('Coil feed','wire',[[28,48],[30,48],[30,65],[34,65]],'gold')
    part('Copper coil','coil',[[34,57],[62,73]],'gold',[48,65])
    part('Coil return','wire',[[62,65],[66,65],[66,93],[12,93],[12,88]],'gold')
    part('Armature pivot','terminal',[[32,46],[36,50]],'steel',[34,48])
    part('Steel armature','contour',[[34,47],[66,47],[66,49],[34,49]],'steel',[34,48])
    part('Return spring','spring',[[63,36],[63,48]],'gold',[63,36])
    part('Load battery','battery',[[82,20],[94,40]],'dark')
    part('Load feed','wire',[[88,20],[88,12],[34,12],[34,48]],'gold')
    tip = [34+32*cos(radians(11)),48+32*sin(radians(11))]
    part('Load contact','terminal',[[tip[0]-1,tip[1]-1],[tip[0]+1,tip[1]+1]],'steel',tip)
    part('Lamp feed','wire',[tip,[75,tip[1]],[75,65],[80,65]],'gold')
    part('Lamp filament','bulb',[[80,54],[96,76]],'white',[88,65])
    part('Lamp return','wire',[[96,65],[99,65],[99,40],[88,40]],'gold')
    actions=[]
    def action(beat,part,effect,amount,start,end):
        actions.append(dict(beat=beat,part=part,effect=effect,amount=[amount,0],start=start,end=end))
    action(1,'Control blade','turn',-30,0,.01)
    action(2,'Control blade','turn',30,.08,.42)
    action(2,'Copper coil','energize',1,.42,.60)
    action(3,'Steel armature','turn',11,.05,.70)
    action(3,'Lamp filament','energize',1,.70,.90)
    action(5,'Control blade','turn',-30,.08,.35)
    action(5,'Copper coil','energize',0,.08,.24)
    action(5,'Steel armature','turn',-11,.24,.85)
    action(5,'Lamp filament','energize',0,.24,.50)
    for name in ('Control feed','Coil feed','Coil return'):
        action(2,name,'current',-1,.42,.43)
        action(5,name,'current',0,.08,.09)
    for name in ('Load feed','Lamp feed','Lamp return'):
        action(3,name,'current',-1,.70,.71)
        action(5,name,'current',0,.24,.25)
    return read_mechanism({'parts':parts,'actions':actions},beats)


class RelayShot(Mechanism3DShot):
    subject='dc-relay'

    def at(self,time,part=None):
        objects,eye,focus=super().at(time,part)
        fraction=min(1.,max(0.,time/max(self.duration-1/30,.01)))
        arm_events=tuple(a for a in self.model.actions if a.part=='Steel armature')
        angle=motion_state(arm_events,self.beat,fraction)[2]
        anchor=self.model.world((63,36))
        end=self.model.world((34+29*cos(angle),48+29*sin(angle)))
        initial=self.model.world((63,48))-anchor
        final=end-anchor
        rotation=atan2(final[1],final[0])-atan2(initial[1],initial[0])
        spring_matrix=translate(*anchor)@spin(rotation)@scale(1,np.linalg.norm(final)/np.linalg.norm(initial),1)@translate(*(-anchor))
        output=[]
        for name,material,matrix,group in objects:
            if group=='Return spring':
                matrix=spring_matrix
            if group=='Control blade' and self.beat<=1:
                pivot=self.model.world((8,48))
                matrix=translate(*pivot)@spin(radians(30))@translate(*(-pivot))
            output.append((name,material,matrix,group))
        self.camera=eye,focus
        return output,eye,focus

    def overlay(self,frame,time):
        draw=ImageDraw.Draw(frame)
        w,h=self.size
        draw.text((w*.07,h*.10),'ELECTROMAGNETIC RELAY',font=_font(round(w*.035)),fill='#edf3e9')
        draw.text((w*.07,h*.14),'CONTROL COIL  /  ISOLATED LAMP CIRCUIT',font=_font(round(w*.025)),fill='#60e0eb')
        eye,focus=self.camera
        projection=_perspective(w/h,.78)@_look_at(eye,focus)
        font=_font(round(w*.024))
        for text,point in [('CONTROL SWITCH',(18,37)),('COIL + IRON CORE',(47,77)),
                           ('ARMATURE',(47,43)),('SPRING',(63,31)),('CONTACT',(72,49)),('LAMP',(88,79))]:
            p=projection@np.append(self.model.world(point,.18),1.)
            x,y=(p[:2]/p[3]*np.array((1,-1))+1)*np.array((w,h))/2
            bounds=draw.textbbox((0,0),text,font=font)
            width=bounds[2]-bounds[0]
            x=min(w-width-10,max(10,x-width/2))
            draw.rounded_rectangle((x-3,y-2,x+width+3,y+w*.031),radius=3,fill='#101b2a')
            draw.text((x,y),text,font=font,fill='#c7d6e2')
        draw.text((w*.07,h*.91),'BLUE: ELECTRON DRIFT - QUALITATIVE CUTAWAY',font=_font(round(w*.022)),fill='#8ba6ba')
