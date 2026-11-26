# SPDX-License-Identifier: MIT
"""Manufactured component surfaces and printed markings, as reusable 3D meshes."""
from functools import lru_cache
from math import cos, sin, tau

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def revolved(profile, center, start=0., end=tau, segments=64):
    """Revolve (height, radius) pairs around Y, with closed profile endpoints."""
    cx,cy,cz = center
    vertices=[]
    for (ya,ra),(yb,rb) in zip(profile,profile[1:]):
        slope=np.array((yb-ya,ra-rb),dtype=float)
        length=np.linalg.norm(slope)
        if length<1e-10:
            continue
        radial,vertical=slope/length
        for index in range(segments):
            a=start+(end-start)*index/segments
            b=start+(end-start)*(index+1)/segments
            for y,r,angle in ((ya,ra,a),(yb,rb,a),(yb,rb,b),(ya,ra,a),(yb,rb,b),(ya,ra,b)):
                vertices.append((cx+r*sin(angle),cy+y,cz+r*cos(angle),
                                 radial*sin(angle),vertical,radial*cos(angle)))
    return np.asarray(vertices,dtype=np.float32)


def smooth_profile(profile,steps=8):
    points=np.asarray(profile,dtype=float)
    smooth=[]
    for i in range(len(points)-1):
        a,b,c,d=points[max(0,i-1)],points[i],points[i+1],points[min(len(points)-1,i+2)]
        for t in np.linspace(0,1,steps,endpoint=False):
            y,r=.5*((2*b)+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t)
            smooth.append((y,max(0.,r)))
    return [*smooth,tuple(points[-1])]


@lru_cache(maxsize=96)
def _letter_runs(text):
    font=ImageFont.load_default(size=48)
    bounds=font.getbbox(text)
    image=Image.new('L',(max(1,bounds[2]-bounds[0]),max(1,bounds[3]-bounds[1])))
    ImageDraw.Draw(image).text((-bounds[0],-bounds[1]),text,font=font,fill=255)
    pixels=np.asarray(image)>100
    runs=[]
    for y,row in enumerate(pixels):
        edges=np.diff(np.pad(row.astype(np.int8),(1,1)))
        for a,b in zip(np.flatnonzero(edges==1),np.flatnonzero(edges==-1)):
            runs.append((a,y,b,y+1))
    return image.size,tuple(runs)


def printed(text, center, width, height, radius=None):
    """Actual surface lettering; curved to fit a cylindrical sleeve when needed."""
    (w,h),runs=_letter_runs(text)
    cx,cy,cz=center
    vertices=[]
    for left,top,right,bottom in runs:
        for start in range(left,right,2 if radius is not None else max(1,right-left)):
            stop=min(right,start+(2 if radius is not None else right-left))
            for px,py in ((start,top),(start,bottom),(stop,bottom),(start,top),(stop,bottom),(stop,top)):
                x=(px/w-.5)*width
                y=(.5-py/h)*height
                if radius is not None:
                    angle=x/radius
                    point=(cx+radius*sin(angle),cy+y,cz+radius*cos(angle))
                    normal=(sin(angle),0.,cos(angle))
                else:
                    point=(cx+x,cy+y,cz)
                    normal=(0.,0.,1.)
                vertices.append((*point,*normal))
    return np.asarray(vertices,dtype=np.float32)


def rounded_route(points, radius=1.3, steps=6):
    """Round bends while keeping the two electrical connection points exact."""
    points=np.asarray(points,dtype=float)
    result=[points[0]]
    for before,corner,after in zip(points,points[1:],points[2:]):
        incoming,outgoing=before-corner,after-corner
        a,b=np.linalg.norm(incoming),np.linalg.norm(outgoing)
        if min(a,b)<1e-8:
            continue
        cut=min(radius,a*.20,b*.20)
        start,end=corner+incoming/a*cut,corner+outgoing/b*cut
        result.append(start)
        for t in np.linspace(0,1,steps+1)[1:]:
            result.append((1-t)**2*start+2*t*(1-t)*corner+t*t*end)
    result.append(points[-1])
    return np.asarray(result)


def route_slice(points, begin, end):
    """Take a length interval along a polyline without changing its end positions."""
    points=np.asarray(points,dtype=float)
    lengths=np.linalg.norm(np.diff(points,axis=0),axis=1)
    cumulative=np.concatenate(([0.],np.cumsum(lengths)))
    total=cumulative[-1]
    begin,end=max(0,begin)*total,min(1,end)*total
    def position(distance):
        index=min(len(lengths)-1,max(0,np.searchsorted(cumulative,distance,side='right')-1))
        return points[index]+(points[index+1]-points[index])*(distance-cumulative[index])/max(lengths[index],1e-9)
    interior=points[(cumulative>begin)&(cumulative<end)]
    return np.vstack((position(begin),interior,position(end)))


def swept_tube(points,radius,sides=12):
    """A continuous cable surface, without a stack of capped cylinders at bends."""
    points=np.asarray(points,dtype=float)
    points=points[np.concatenate(([True],np.linalg.norm(np.diff(points,axis=0),axis=1)>1e-8))]
    if len(points)<2:
        raise ValueError('A tube needs two distinct endpoints')
    tangent=np.gradient(points,axis=0)
    invalid=np.linalg.norm(tangent,axis=1)<1e-9
    tangent[invalid]=np.concatenate((np.diff(points,axis=0),[points[-1]-points[-2]]))[invalid]
    tangent/=np.linalg.norm(tangent,axis=1,keepdims=True)
    first=np.cross(tangent[0],(0,0,1) if abs(tangent[0,2])<.95 else (0,1,0))
    normals=[]
    for direction in tangent:
        first=first-direction*np.dot(first,direction)
        first/=max(np.linalg.norm(first),1e-9)
        second=np.cross(direction,first)
        normals.append([first*cos(tau*i/sides)+second*sin(tau*i/sides) for i in range(sides)])
    normals=np.asarray(normals)
    rings=points[:,None,:]+radius*normals
    vertices=[]
    for index in range(len(points)-1):
        for side in range(sides):
            following=(side+1)%sides
            for row,column in ((index,side),(index+1,side),(index+1,following),
                               (index,side),(index+1,following),(index,following)):
                vertices.append((*rings[row,column],*normals[row,column]))
    for row,sign in ((0,-1),(-1,1)):
        for side in range(sides):
            for point in (points[row],rings[row,side],rings[row,(side+1)%sides]):
                vertices.append((*point,*(tangent[row]*sign)))
    return np.asarray(vertices,dtype=np.float32)
