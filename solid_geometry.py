# SPDX-License-Identifier: MIT
"""Validated compound geometry for prompt-defined parts, independent of topics."""
from dataclasses import dataclass
from functools import lru_cache
from math import isfinite
import copy
import re

import numpy as np
from PIL import ImageColor

from cinematic_geometry import mesh


PRIMITIVES=('box','cylinder','sphere','ring','shell')


@dataclass(frozen=True)
class SolidPiece:
    primitive: str
    center: tuple
    size: tuple
    axis: str
    color: str

    def data(self):
        return dict(primitive=self.primitive,center=list(self.center),size=list(self.size),axis=self.axis,color=self.color)


def solid_schema(colors):
    triple=lambda lo,hi:dict(type='array',minItems=3,maxItems=3,items=dict(type='number',minimum=lo,maximum=hi))
    return dict(type='array',minItems=1,maxItems=6,items=dict(type='object',additionalProperties=False,
        properties=dict(primitive=dict(type='string',enum=list(PRIMITIVES)),center=triple(0,1),
                        size=triple(.02,1),axis=dict(type='string',enum=['x','y','z']),
                        color=dict(type='string',enum=list(colors))),
        required=['primitive','center','size','axis','color']))


def read_solids(value,name,colors):
    if not isinstance(value,list) or not 1<=len(value)<=6:
        raise ValueError(f'{name}: solid geometry needs 1..6 modeled pieces')
    result=[]
    for i,item in enumerate(value):
        if not isinstance(item,dict):raise ValueError(f'{name}.geometry[{i}] must be a primitive object')
        vectors=[]
        for field,lo,hi in (('center',0,1),('size',.02,1)):
            numbers=item.get(field)
            if (not isinstance(numbers,list) or len(numbers)!=3
                    or any(type(x) not in (int,float) or not lo<=x<=hi or not isfinite(x) for x in numbers)):
                raise ValueError(f'{name}.geometry[{i}].{field} needs three finite numbers from {lo} to {hi}')
            vectors.append(tuple(numbers))
        center,size=vectors
        if any(c-s/2 < -1e-6 or c+s/2 > 1+1e-6 for c,s in zip(center,size)):
            raise ValueError(f'{name}.geometry[{i}] extends outside its part: center +/- size/2 must fit 0..1')
        if item.get('primitive') not in PRIMITIVES or item.get('axis') not in ('x','y','z') or item.get('color') not in colors:
            raise ValueError(f'{name}.geometry[{i}] has an unsupported primitive, axis or material color')
        result.append(SolidPiece(item['primitive'],center,size,item['axis'],item['color']))
    return tuple(result)


def fit_solids(value):
    """Recover a generated compound expressed in different local units.

    Fit all pieces together; never move their centres independently. A modeled
    surface gets finite thickness, but an entirely zero-size object is rejected.
    The strict reader still checks names, materials, types and nonfinite data.
    """
    result=copy.deepcopy(value)
    if not isinstance(result,list) or not 1<=len(result)<=6:return result
    changed=False
    for item in result:
        if not isinstance(item,dict):return result
        for key in ('center','size'):
            vector=item.get(key)
            if (not isinstance(vector,list) or len(vector)!=3 or
                    any(type(x) not in (int,float) or abs(x)>10000 or not isfinite(x) for x in vector)):return result
        size=item['size']
        if min(size)<0 or max(size)==0:return result
        if min(size)<.02:
            item['size']=[max(s,.02*max(size)) for s in size];changed=True
    lo=np.min([np.array(p['center'])-np.array(p['size'])/2 for p in result],axis=0)
    hi=np.max([np.array(p['center'])+np.array(p['size'])/2 for p in result],axis=0)
    if changed or min(lo)<0 or max(hi)>1 or any(max(p['size'])>1 for p in result):
        factor=.96/max(hi-lo);centre=(lo+hi)/2
        for p in result:
            p['center']=(.5+(np.array(p['center'])-centre)*factor).tolist()
            p['size']=np.maximum(.02,np.array(p['size'])*factor).tolist()
    return result


@lru_cache(maxsize=12)
def _unit_mesh(primitive,axis):
    source={'box':'beveled-box','cylinder':'cylinder','sphere':'sphere','ring':'groove','shell':'shell'}[primitive]
    vertices=np.asarray(mesh(source),dtype=np.float64).copy()
    rotation=np.eye(3)
    if axis=='x':rotation=np.array([[0,0,1],[0,1,0],[-1,0,0]])
    if axis=='y':rotation=np.array([[1,0,0],[0,0,1],[0,-1,0]])
    vertices[:,:3]=vertices[:,:3]@rotation.T
    vertices[:,3:]=vertices[:,3:]@rotation.T
    lo=vertices[:,:3].min(axis=0);hi=vertices[:,:3].max(axis=0)
    extent=hi-lo
    vertices[:,:3]=(vertices[:,:3]-(lo+hi)/2)/extent
    vertices[:,3:]*=extent
    vertices[:,3:]/=np.linalg.norm(vertices[:,3:],axis=1,keepdims=True)
    vertices.setflags(write=False)
    return vertices


def solid_meshes(component,world,palette):
    left,top=np.min(component.points,axis=0);right,bottom=np.max(component.points,axis=0)
    unit=np.linalg.norm(world((1,0))-world((0,0)))
    w,h=(right-left)*unit,(bottom-top)*unit
    depth=min(w,h)*.75
    result=[]
    cutaway=bool(re.search(r'\b(?:housing|casing|enclosure|case|shell)\b',component.part.label,re.I))
    for piece in component.geometry:
        vertices=_unit_mesh(piece.primitive,piece.axis).copy()
        if cutaway and piece.primitive in ('box','cylinder','sphere'):
            triangles=vertices.reshape(-1,3,6)
            # Remove the camera-facing wall of an educational cutaway instead
            # of allowing an opaque casing to hide every working part inside.
            vertices=triangles[triangles[:,:,5].mean(axis=1)<=.15].reshape(-1,6).copy()
        cx,cy,cz=piece.center
        centre=world((left+cx*(right-left),top+cy*(bottom-top)),(cz-.5)*depth)
        dimensions=np.array((w,h,depth))*piece.size
        vertices[:,:3]=vertices[:,:3]*dimensions+centre
        vertices[:,3:]/=dimensions
        vertices[:,3:]/=np.linalg.norm(vertices[:,3:],axis=1,keepdims=True)
        color=np.array(ImageColor.getrgb(palette[piece.color]))/255
        metal=.78 if piece.color in ('steel','dark','gold','white') else .25
        result.append((vertices.astype(np.float32),(*color,metal)))
    if component.electrical_role:
        for x in (left,right):
            vertices=_unit_mesh('cylinder','z').copy()
            dimensions=np.array((.07,.07,.06))
            vertices[:,:3]=vertices[:,:3]*dimensions+world((x,(top+bottom)/2),.055)
            vertices[:,3:]/=dimensions
            vertices[:,3:]/=np.linalg.norm(vertices[:,3:],axis=1,keepdims=True)
            result.append((vertices.astype(np.float32),(.84,.37,.15,.8)))
    return result
