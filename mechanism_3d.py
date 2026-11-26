# SPDX-License-Identifier: MIT
"""Render model-planned part profiles as solid, continuously moving 3D parts."""

from math import cos, sin, tan, tau

import mapbox_earcut
import numpy as np
from PIL import ImageColor

from cinematic_geometry import scale, spin, translate
from mechanism_animation import ELECTRICAL_SHAPES, _bounds, _outline, biological_level, current_level, motion_state
from biological_components import BIOLOGICAL_SHAPES, biological_mesh, biological_parts, biological_route
from electrical_components import electrical_meshes
from electrical_detail import rounded_route, swept_tube


def extrude_profile(points, depth=.18):
    """Triangulate concave profiles and add closed walls and bevelled edges."""
    points = np.asarray(points,dtype=np.float64)
    if len(points)>1 and np.allclose(points[0],points[-1]):
        points = points[:-1]
    if len(points)<3 or not np.isfinite(points).all():
        raise ValueError("A 3D part needs a complete, finite outline")
    area = np.sum(points[:,0]*np.roll(points[:,1],-1)-points[:,1]*np.roll(points[:,0],-1))/2
    if abs(area)<1e-6:
        raise ValueError("A 3D part outline has no usable area")
    if area<0:
        points = points[::-1].copy()
    centre = points.mean(axis=0)
    face = centre+(points-centre)*.982
    triangles = mapbox_earcut.triangulate_float64(face,np.array([len(face)],dtype=np.uint32))
    if not len(triangles):
        raise ValueError("The part outline could not be triangulated")
    vertices = []
    for side in (-1.,1.):
        for index in triangles:
            vertices.append((*face[index],side*depth/2,0.,0.,side))
    bevel = min(.022,depth*.18)
    profiles = ((face,-depth/2),(points,-depth/2+bevel),
                (points,depth/2-bevel),(face,depth/2))
    for (a,za),(b,zb) in zip(profiles,profiles[1:]):
        for index in range(len(points)):
            following = (index+1)%len(points)
            edge = points[following]-points[index]
            length = np.linalg.norm(edge)
            if length<1e-9:
                continue
            normal = np.array((edge[1]/length,-edge[0]/length,0.))
            if za == -depth/2:
                normal = (normal+[0,0,-1])/np.sqrt(2)
            elif zb == depth/2:
                normal = (normal+[0,0,1])/np.sqrt(2)
            for xy,z in ((a[index],za),(a[following],za),(b[following],zb),
                         (a[index],za),(b[following],zb),(b[index],zb)):
                vertices.append((*xy,z,*normal))
    return np.asarray(vertices,dtype=np.float32)


def _wire(points,radius):
    return swept_tube(points,radius)


class Mechanism3D:
    def __init__(self, mechanism):
        self.parts,self.actions = mechanism
        left,top,right,bottom = _bounds(mechanism)
        self.centre = ((left+right)/2,(top+bottom)/2)
        self.unit = .042
        self.radius_x = max(.7,(right-left)*self.unit/2)
        self.radius_y = max(.6,(bottom-top)*self.unit/2)
        self.floor = -(bottom-self.centre[1])*self.unit-.26
        self.compiled = []
        self.roles = {}
        self.routes = {}
        electrical = any(part.shape in (*ELECTRICAL_SHAPES,*BIOLOGICAL_SHAPES) for part in self.parts)
        for index,component in enumerate(self.parts):
            name = "custom-cutaway-"+str(index)
            z = 0. if electrical else index*.055
            events = tuple(action for action in self.actions if action.part==component.part.label)
            if component.shape in BIOLOGICAL_SHAPES:
                route=biological_route(component)
                if route is not None:
                    self.routes[component.part.label]=np.array([self.world(point,.075) for point in route])
                for piece,(vertices,material,role) in enumerate(biological_parts(component,self.world)):
                    piece_name=name+'-'+str(piece)
                    self.roles[piece_name]=role
                    self.compiled.append((component,events,piece_name,vertices,material,z))
                continue
            if component.shape == 'wire':
                self.routes[component.part.label]=np.array([self.world(point,.085) for point in rounded_route(component.points)])
            if component.shape in ELECTRICAL_SHAPES:
                for piece,(vertices,material,role) in enumerate(electrical_meshes(component,self.world,_wire)):
                    piece_name = name+"-"+str(piece)
                    self.roles[piece_name] = role
                    self.compiled.append((component,events,piece_name,vertices,material,z))
                continue
            points = [self.world(point,z) for point in _outline(component)]
            if component.shape == "spring":
                start,end = (self.world(point,z) for point in component.points[:2])
                direction = end-start
                length = np.linalg.norm(direction)
                if length<1e-7:
                    raise ValueError("A spring needs a visible length")
                side = np.array((-direction[1],direction[0],0.))/length
                coil = [start+direction*(step/100)+.11*(side*cos(tau*6*step/100)
                         +np.array((0.,0.,1.))*sin(tau*6*step/100)) for step in range(101)]
                vertices = _wire([start,*coil,end],.021)
            elif component.shape in ("pipe","path","wire"):
                vertices = _wire(points,.049 if component.shape=="pipe" else .026)
            else:
                vertices = extrude_profile([point[:2] for point in points])
                vertices[:,2] += z
            color = np.array(ImageColor.getrgb(component.color))/255
            metal = .78 if component.color in ("#91aabd","#30485f","#edf3e9","#eab15b") else .32
            events = tuple(action for action in self.actions if action.part==component.part.label)
            self.compiled.append((component,events,name,vertices,(*color,metal),z))

    def world(self, point, z=0.):
        return np.array(((point[0]-self.centre[0])*self.unit,
                         (self.centre[1]-point[1])*self.unit,z))

    def upload(self, renderer):
        for _,_,name,vertices,_,_ in self.compiled:
            renderer.register_mesh(name,vertices)
        if any(part.shape in BIOLOGICAL_SHAPES for part in self.parts):
            renderer.register_mesh('bio-rbc',biological_mesh('bio-rbc'))
            renderer.register_mesh('bio-marker',biological_mesh('sphere'))


class Mechanism3DShot:
    subject = "mechanism-3d"
    caption = None

    def __init__(self, model, size, beat, view="wide", duration=3., offset=0.):
        self.model,self.size,self.beat,self.view = model,size,beat,view
        self.duration,self.offset,self.floor = duration,offset,model.floor

    def at(self, time, part=None):
        fraction = min(1.,max(0.,time/max(self.duration-1/30,.01)))
        objects = []
        flow_parts=set()
        for component,events,name,_,material,z in self.model.compiled:
            dx,dy,turn,sx,sy,heat,flow = motion_state(events,self.beat,fraction)
            dissolved=biological_level(events,'dissolve',self.beat,fraction)
            biological_scale=1.
            for action in events:
                if action.effect=='pulse' and (action.beat<self.beat or action.beat==self.beat and fraction>=action.start):
                    hz,amplitude=action.amount
                    biological_scale=1+amplitude*sin(tau*hz*(self.offset+time))
            if dissolved>=.999:
                continue
            role = self.model.roles.get(name)
            if role == 'internal' and self.view != 'detail':
                continue
            if role in ('shell_front','shell_print') and self.view == 'detail' and component.shape in ('battery','capacitor'):
                continue
            if role == 'can_top' and self.view == 'detail' and component.shape == 'capacitor':
                continue
            if role == "field" and heat <= .02:
                continue
            if component.shape == "motor" and role != "rotor":
                turn = 0.
            pivot = self.model.world(component.pivot)
            movement = np.array((dx,-dy,0.))*self.model.unit
            factor=biological_scale*max(.025,1-dissolved)**(1/3)
            matrix = translate(*(pivot+movement))@spin(-turn)@scale(sx*factor,sy*factor,factor)@translate(*(-pivot))
            if heat and (component.shape not in ("bulb","led","coil","relay") or role == "filament"):
                color = np.array(material[:3])*(1-heat)+np.array((1.,.38,.10))*heat
                material = (*color,7. if heat>.75 else material[3])
            objects.append((name,material,matrix,component.part.label))
            current = current_level(events,self.beat,fraction)
            # Absolute time prevents particles jumping back at narration cuts.
            phase = (self.offset+time)*.21*current if current else flow*2
            if (flow or current) and component.part.label not in flow_parts:
                flow_parts.add(component.part.label)
                points = self.model.routes.get(component.part.label)
                if points is None:
                    points = [self.model.world(point,z+.07) for point in component.points]
                lengths = np.linalg.norm(np.diff(points,axis=0),axis=1)
                total = sum(lengths)
                for index in range(5):
                    remaining = ((phase+index/5)%1)*total
                    for a,b,length in zip(points,points[1:],lengths):
                        if length and remaining<=length:
                            point = a+(b-a)*remaining/length
                            native_blood=component.shape=='blood_vessel'
                            objects.append(('bio-rbc' if native_blood else "sphere",(.70,.04,.06,.08) if native_blood else (.40,.92,1.,7.),
                                            matrix@translate(*point)@scale(.043,.034,.035) if native_blood else matrix@translate(*point)@scale(.024,.024,.024),component.part.label))
                            break
                        remaining -= length
        aspect = self.size[0]/self.size[1]
        distance = max(self.model.radius_y,self.model.radius_x/aspect)/tan(.78/2)*1.18
        if self.view == "overhead":
            eye = (distance*.10,distance*.53,distance*.86)
        else:
            eye = (distance*.18,distance*.16,distance*(.96 if self.view=="detail" else 1.))
        return objects,eye,np.array((0.,0.,.12))
