# SPDX-License-Identifier: MIT
"""Render model-planned part profiles as solid, continuously moving 3D parts."""

from math import cos, sin, tan, tau

import mapbox_earcut
import numpy as np
from PIL import ImageColor

from cinematic_geometry import mesh, scale, spin, translate, tube
from mechanism_animation import _bounds, _outline, motion_state


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
    cylinder = np.asarray(mesh("cylinder"),dtype=np.float32)
    pieces = []
    for a,b in zip(points,points[1:]):
        if np.linalg.norm(np.asarray(b)-a)<1e-7:
            continue
        matrix = tube(a,b,radius)
        positions = cylinder[:,:3]@matrix[:3,:3].T+matrix[:3,3]
        normals = cylinder[:,3:]@np.linalg.inv(matrix[:3,:3])
        normals /= np.linalg.norm(normals,axis=1,keepdims=True)
        pieces.append(np.column_stack((positions,normals)))
    if not pieces:
        raise ValueError("A tube needs two distinct endpoints")
    return np.concatenate(pieces).astype(np.float32)


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
        for index,component in enumerate(self.parts):
            name = "custom-cutaway-"+str(index)
            z = index*.055
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
            elif component.shape in ("pipe","path"):
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


class Mechanism3DShot:
    subject = "mechanism-3d"
    caption = None

    def __init__(self, model, size, beat, view="wide", duration=3., offset=0.):
        self.model,self.size,self.beat,self.view = model,size,beat,view
        self.duration,self.offset,self.floor = duration,offset,model.floor

    def at(self, time, part=None):
        fraction = min(1.,max(0.,time/max(self.duration-1/30,.01)))
        objects = []
        for component,events,name,_,material,z in self.model.compiled:
            dx,dy,turn,sx,sy,heat,flow = motion_state(events,self.beat,fraction)
            pivot = self.model.world(component.pivot)
            movement = np.array((dx,-dy,0.))*self.model.unit
            matrix = translate(*(pivot+movement))@spin(-turn)@scale(sx,sy,1.)@translate(*(-pivot))
            if heat:
                color = np.array(material[:3])*(1-heat)+np.array((1.,.38,.10))*heat
                material = (*color,7. if heat>.75 else material[3])
            objects.append((name,material,matrix,component.part.label))
            if flow:
                points = [self.model.world(point,z+.07) for point in component.points]
                lengths = np.linalg.norm(np.diff(points,axis=0),axis=1)
                total = sum(lengths)
                for index in range(5):
                    remaining = ((flow*2+index/5)%1)*total
                    for a,b,length in zip(points,points[1:],lengths):
                        if length and remaining<=length:
                            point = a+(b-a)*remaining/length
                            objects.append(("sphere",(.40,.92,1.,7.),
                                            matrix@translate(*point)@scale(.024,.024,.024),component.part.label))
                            break
                        remaining -= length
        aspect = self.size[0]/self.size[1]
        distance = max(self.model.radius_y,self.model.radius_x/aspect)/tan(.78/2)*1.18
        if self.view == "overhead":
            eye = (distance*.10,distance*.53,distance*.86)
        else:
            eye = (distance*.18,distance*.16,distance*(.96 if self.view=="detail" else 1.))
        return objects,eye,np.array((0.,0.,.12))
