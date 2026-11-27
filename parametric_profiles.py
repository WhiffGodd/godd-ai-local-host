# SPDX-License-Identifier: MIT
"""Closed profiles for reusable revolved and extruded manufactured parts."""
from math import isfinite,cos,sin,tau
import numpy as np


def read_profile(value,name):
    if not isinstance(value,list) or not 3<=len(value)<=32:raise ValueError(f'{name}: profile needs 3..32 outline points')
    points=[]
    for i,p in enumerate(value):
        if (not isinstance(p,list) or len(p)!=2 or any(type(v) not in (float,int) or not 0<=v<=1 or not isfinite(v) for v in p)):
            raise ValueError(f'{name}.profile[{i}] needs two finite numbers from 0 to 1')
        points.append(tuple(p))
    if points[0]==points[-1]:points.pop()
    if len(points)<3 or len(set(points))!=len(points):raise ValueError(f'{name}: profile contains duplicate points')
    area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(points,points[1:]+points[:1]))/2
    if abs(area)<1e-5:raise ValueError(f'{name}: profile has no area')
    def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    def intersects(a,b,c,d):
        aa,bb,cc,dd=cross(a,b,c),cross(a,b,d),cross(c,d,a),cross(c,d,b)
        if aa*bb<0 and cc*dd<0:return True
        def on(p,a,b):return min(a[0],b[0])-1e-8<=p[0]<=max(a[0],b[0])+1e-8 and min(a[1],b[1])-1e-8<=p[1]<=max(a[1],b[1])+1e-8
        return any(abs(v)<1e-8 and on(p,x,y) for v,p,x,y in ((aa,c,a,b),(bb,d,a,b),(cc,a,c,d),(dd,b,c,d)))
    n=len(points)
    for i in range(n):
        for j in range(i+1,n):
            if j in (i,(i+1)%n) or (j+1)%n==i:continue
            if intersects(points[i],points[(i+1)%n],points[j],points[(j+1)%n]):raise ValueError(f'{name}: profile crosses itself')
    return tuple(points if area>0 else reversed(points))


def profile_mesh(kind,profile,segments=64):
    result=[]
    def triangle(points,normals):
        a,b,c=np.asarray(points)
        if np.linalg.norm(np.cross(b-a,c-a))<1e-10:return
        result.extend((*point,*normal) for point,normal in zip(points,normals))
    if kind=='lathe':
        for a,b in zip(profile,(*profile[1:],profile[0])):
            dr=(b[0]-a[0])*.5;dz=b[1]-a[1];length=(dr*dr+dz*dz)**.5
            for i in range(segments):
                t0,t1=tau*i/segments,tau*(i+1)/segments
                def point(p,t):return (p[0]*.5*cos(t),p[0]*.5*sin(t),p[1]-.5)
                def normal(t):return (dz*cos(t)/length,dz*sin(t)/length,-dr/length)
                p0,p1,p2,p3=point(a,t0),point(a,t1),point(b,t1),point(b,t0)
                n0,n1=normal(t0),normal(t1)
                triangle((p0,p1,p2),(n0,n1,n1));triangle((p0,p2,p3),(n0,n1,n0))
    elif kind=='extrude':
        import mapbox_earcut
        points=np.array([(x-.5,.5-y) for x,y in reversed(profile)],dtype=np.float64)
        indexes=mapbox_earcut.triangulate_float64(points,np.array([len(points)],dtype=np.uint32))
        for sign in (-1,1):
            for a,b,c in np.asarray(indexes).reshape(-1,3):
                ids=(a,b,c) if sign>0 else (c,b,a)
                triangle([(*points[i],sign*.5) for i in ids],[(0,0,sign)]*3)
        for a,b in zip(points,np.roll(points,-1,axis=0)):
            edge=b-a;normal=(edge[1],-edge[0],0);normal=np.array(normal)/np.linalg.norm(normal)
            p0,p1,p2,p3=(*a,-.5),(*b,-.5),(*b,.5),(*a,.5)
            triangle((p0,p1,p2),(normal,)*3);triangle((p0,p2,p3),(normal,)*3)
    else:raise ValueError('Unsupported profile operation')
    if not result:raise ValueError('Profile produced an empty surface')
    return np.asarray(result,dtype=np.float64)
