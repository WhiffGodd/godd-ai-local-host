# SPDX-License-Identifier: MIT
"""Reusable anatomy for educational cutaways; dimensions are schematic."""
from functools import lru_cache
from math import cos, sin, tau, pi

import numpy as np

from cinematic_geometry import scale, translate, tube
from electrical_detail import rounded_route, swept_tube


BIOLOGICAL_SHAPES = ('tablet','capsule','esophagus','stomach','intestine','villus',
                     'blood_vessel','red_blood_cell','liver','kidney','heart','lung',
                     'alveolus','cell','membrane','receptor','neuron','torso','food_bolus','ureter','bladder','head','mouth','digestive_tube')
TISSUE=(.72,.30,.28,.06)
MUCOSA=(.89,.48,.40,.03)
BLOOD=(.65,.035,.045,.10)
VESSEL=(.72,.16,.21,8.)


def _surface(fn,rows=24,columns=32):
    """Smooth surface normals from the parametric tangent directions."""
    grid=[]
    for i in range(rows+1):
        row=[]
        for j in range(columns+1):
            u,v=i/rows,j/columns
            point=np.asarray(fn(u,v),dtype=float)
            a=np.asarray(fn(min(1.,u+.0001),v))-fn(max(0.,u-.0001),v)
            b=np.asarray(fn(u,(v+.0001)%1))-fn(u,(v-.0001)%1)
            normal=np.cross(b,a)
            length=np.linalg.norm(normal)
            if length<1e-10:
                normal=np.array((0.,1. if u<.5 else -1.,0.))
            else:
                normal/=length
            row.append((*point,*normal))
        grid.append(row)
    return np.asarray([vertex for i in range(rows) for j in range(columns)
                       for vertex in (grid[i][j],grid[i+1][j],grid[i+1][j+1],
                                      grid[i][j],grid[i+1][j+1],grid[i][j+1])],dtype=np.float32)


@lru_cache(maxsize=4)
def biological_mesh(name):
    if name=='bio-rbc':
        def rbc(u,v):
            angle=tau*v
            t=pi*u
            radius=sin(t)
            # Biconcave disc: thick rim and a depressed centre on BOTH faces.
            z=cos(t)*(.12+.32*sin(t)**2)
            return (radius*cos(angle),radius*sin(angle),z)
        return _surface(rbc,18,28)
    def sphere(u,v):
        return (sin(pi*u)*cos(tau*v),cos(pi*u),sin(pi*u)*sin(tau*v))
    return _surface(sphere,18,28)


def _closed_curve(points,count=80):
    points=np.asarray(points,dtype=float)
    curve=[]
    for t in np.linspace(0,len(points),count,endpoint=False):
        i=int(t);f=t-i
        a,b,c,d=(points[(i+offset)%len(points)] for offset in (-1,0,1,2))
        curve.append(.5*((2*b)+(-a+c)*f+(2*a-5*b+4*c-d)*f*f+(-a+3*b-3*c+d)*f*f*f))
    return np.asarray(curve)


def _loft(outline,center,depth,front=True):
    curve=_closed_curve(outline)
    sign=1 if front else -1
    def shape(u,v):
        t=v*len(curve)
        index=int(t)%len(curve)
        edge=curve[index]+(curve[(index+1)%len(curve)]-curve[index])*(t-int(t))
        amount=sin(pi*u/2)
        point=np.array((*(center[:2]+(edge-center[:2])*amount),center[2]+sign*depth*cos(pi*u/2)))
        return point
    vertices=_surface(shape,16,80)
    if not front:
        vertices[:,3:]*=-1
    return vertices


def biological_route(component):
    points=np.asarray(component.points)
    left,top=points.min(axis=0);right,bottom=points.max(axis=0)
    cx,cy=(left+right)/2,(top+bottom)/2
    if component.shape=='esophagus':
        return np.array([(cx,top+(bottom-top)*i/26) for i in range(27)])
    if component.shape=='intestine':
        # Broad U-bends leave room for the bowel's physical radius. Tight sine
        # reversals self-intersect and turn a thick tube into spikes.
        xmin,xmax=left+(right-left)*.17,right-(right-left)*.17
        dy=(bottom-top)*.78/3
        y=top+(bottom-top)*.11
        route=[(xmin,y)]
        for row in range(4):
            side=1 if row%2==0 else -1
            x=xmax if side>0 else xmin
            route.append((x,y))
            if row<3:
                r=dy/2
                route.extend((x+side*r*cos(angle),y+r+r*sin(angle)) for angle in np.linspace(-pi/2,pi/2,25)[1:])
                y+=dy
        return np.asarray(route)
    if component.shape in ('blood_vessel','ureter','digestive_tube'):
        return rounded_route(points) if len(points)>2 else np.array(((left,cy),(right,cy)))
    if component.shape=='neuron':
        return np.array(((cx,cy),(right,cy)))
    return None


def biological_parts(component,world):
    points=np.asarray(component.points)
    left,top=points.min(axis=0);right,bottom=points.max(axis=0)
    cx,cy=(left+right)/2,(top+bottom)/2
    u=np.linalg.norm(world((1,0))-world((0,0)))
    w,h=(right-left)*u,(bottom-top)*u
    out=[]

    def solid(name,point,dimensions,color,role='body',z=0.):
        vertices=biological_mesh(name).copy()
        matrix=translate(*world(point,z))@scale(*dimensions)
        vertices[:,:3]=vertices[:,:3]@matrix[:3,:3].T+matrix[:3,3]
        vertices[:,3:]=vertices[:,3:]@np.linalg.inv(matrix[:3,:3])
        vertices[:,3:]/=np.linalg.norm(vertices[:,3:],axis=1,keepdims=True)
        out.append((vertices,color,role))

    def line(route,radius,color,role='body',z=0.):
        out.append((swept_tube([world(point,z) for point in route],radius),color,role))

    def organ(outline,color=TISSUE,depth=.15,box=None):
        l,t,r,b=box or (left,top,right,bottom)
        outline=np.array([world((l+(x+.5)*(r-l),t+(.5-y)*(b-t)),0)[:2] for x,y in outline])
        center=world(((l+r)/2,(t+b)/2))
        out.append((_loft(outline,center,depth,False),color,'organ_back'))
        out.append((_loft(outline,center,depth,True),(*color[:3],9.),'organ_front'))
        rim=np.array([(*p,.0) for p in _closed_curve(outline)])
        out.append((swept_tube([*rim,rim[0]],.018),MUCOSA,'rim'))

    kind=component.shape
    if kind in ('tablet','capsule'):
        # A convex compressed tablet or a two-tone hard capsule with a joining seam.
        if kind=='tablet':
            solid('sphere',(cx,cy),(w*.48,h*.42,min(w,h)*.26),(.94,.92,.85,.02),'medicine')
            line([(cx-(right-left)*.28,cy),(cx+(right-left)*.28,cy)],.009,(.52,.50,.44,.03),'score',z=min(w,h)*.265)
        else:
            solid('sphere',(cx,cy),(w*.48,h*.42,min(w,h)*.34),(.92,.80,.54,.06),'medicine')
            # Front cap covers half of the cylindrical joining region.
            solid('sphere',(cx-(right-left)*.18,cy),(w*.29,h*.42,min(w,h)*.345),(.16,.44,.66,.08),'medicine')
            ring=[world((cx,cy+(bottom-top)*.40*cos(tau*i/40)),min(w,h)*.35*sin(tau*i/40)) for i in range(41)]
            out.append((swept_tube(ring,.008),(.72,.66,.51,.08),'seam'))
    elif kind in ('esophagus','blood_vessel','intestine','ureter','digestive_tube'):
        if kind=='intestine':
            route=biological_route(component)
            radius=min(w*.045,h*.072)
        elif kind=='esophagus':
            route=biological_route(component)
            radius=w*.42
        else:
            route=biological_route(component)
            radius=.042 if kind=='ureter' else .095
        line(route,radius,VESSEL if kind=='blood_vessel' else (*TISSUE[:3],8.),'lumen')
        line(route,max(.012,radius*.42),(.73,.63,.31,.03) if kind=='ureter' else (.48,.07,.10,.03),'lumen_back',z=-radius*.5)
        if kind=='esophagus':
            for index,point in enumerate(route):
                ring=[world((point[0]+radius/u*cos(tau*i/24),point[1]),radius*sin(tau*i/24)) for i in range(25)]
                out.append((swept_tube(ring,.009),TISSUE,f'band:{index}'))
        elif kind=='intestine':
            # Segmented mucosal folds follow the actual coiled bowel.
            for index in range(2,len(route)-2,5):
                p=np.array(route[index]);direction=np.array(route[index+1])-route[index-1]
                direction/=np.linalg.norm(direction)
                side=np.array((-direction[1],direction[0]))*radius/u
                curve=[world(p+side*cos(tau*i/20),radius*sin(tau*i/20)) for i in range(21)]
                out.append((swept_tube(curve,.008),MUCOSA,'fold'))
    elif kind=='stomach':
        organ([(-.23,.50),(-.01,.41),(.18,.49),(.43,.37),(.48,.05),(.36,-.24),
               (.14,-.45),(-.17,-.45),(-.45,-.22),(-.47,-.05),(-.30,-.09),(-.15,-.26),
               (.04,-.23),(-.09,-.06),(-.20,.15)],depth=min(w,h)*.26)
        for index in range(7):
            x=left+(right-left)*(.35+index*.065)
            route=[(x+(right-left)*.035*sin(tau*t),top+(bottom-top)*(.28+.47*t)) for t in np.linspace(0,1,24)]
            line(route,.012,(.68,.22,.20,.03),'rugae',z=.018)
    elif kind=='liver':
        organ([(-.5,.19),(-.28,.43),(.08,.46),(.48,.30),(.43,.02),(.12,-.15),
               (-.05,-.40),(-.37,-.28)],(.47,.14,.14,.05),depth=min(w,h)*.23)
        line([(cx,top+(bottom-top)*.22),(cx-(right-left)*.13,cy),(cx-(right-left)*.02,bottom)],.017,(.23,.055,.06,.02),'fissure',z=.06)
    elif kind=='kidney':
        organ([(-.10,.46),(.22,.46),(.45,.19),(.42,-.20),(.15,-.48),(-.16,-.41),
               (-.32,-.15),(-.08,-.04),(-.08,.09),(-.32,.23)],(.55,.18,.19,.03),depth=w*.23)
        for index in range(7):
            a=-pi*.65+index*pi*.22
            line([(cx,cy),(cx+cos(a)*(right-left)*.28,cy+sin(a)*(bottom-top)*.30)],.014,MUCOSA,'renal_pyramid',z=.03)
    elif kind=='heart':
        organ([(-.05,.40),(.17,.47),(.39,.29),(.46,-.05),(.22,-.44),(-.04,-.49),
               (-.35,-.12),(-.45,.17),(-.30,.40)],(.67,.20,.23,.04),depth=w*.28)
        line([(cx,cy),(cx-(right-left)*.16,cy+(bottom-top)*.15),(cx-(right-left)*.10,bottom)],.017,(.85,.56,.41,.05),'coronary',z=.12)
    elif kind=='bladder':
        organ([(-.39,.20),(-.24,.45),(.24,.45),(.39,.20),(.28,-.18),(.10,-.44),
               (-.10,-.44),(-.28,-.18)],(.77,.41,.36,.04),depth=w*.25)
        line([(cx,cy+(bottom-top)*.30),(cx,bottom)],.018,MUCOSA,'urethra')
    elif kind in ('lung','alveolus'):
        if kind=='lung':
            outline=[(.06,.49),(-.29,.28),(-.45,-.08),(-.35,-.40),(.23,-.44),(.39,-.22),(.30,.12)]
            for sign in (-1,1):
                if sign<0:
                    box=(left,top,cx-(right-left)*.035,bottom)
                    profile=outline
                else:
                    box=(cx+(right-left)*.035,top,right,bottom)
                    profile=[(-x,y) for x,y in outline]
                organ(profile,(.76,.42,.40,.03),depth=w*.13,box=box)
                for offset in (.22,.60):
                    x=cx+sign*(right-left)*.25
                    y=top+(bottom-top)*offset
                    line([(cx+sign*(right-left)*.10,y),(x,y+(bottom-top)*.12),(cx+sign*(right-left)*.43,y+(bottom-top)*.18)],.010,(.49,.20,.22,.03),'fissure',z=.075)
            line([(cx,top),(cx,cy-(bottom-top)*.18)],.05,MUCOSA,'trachea')
            for sign in (-1,1):
                root=(cx+sign*(right-left)*.20,cy)
                line([(cx,cy-(bottom-top)*.18),root],.035,MUCOSA,'bronchus')
                for direction in (-1,1):
                    branch=(cx+sign*(right-left)*.33,cy+direction*(bottom-top)*.20)
                    line([root,branch],.022,MUCOSA,'bronchiole')
                    for dy in (-.08,.08):
                        line([branch,(cx+sign*(right-left)*.40,branch[1]+dy*(bottom-top))],.012,MUCOSA,'bronchiole')
        else:
            for index,(x,y) in enumerate(((-.24,.08),(.06,-.18),(.26,.09),(-.12,.30),(.17,.32))):
                solid('sphere',(cx+x*(right-left),cy+y*(bottom-top)),(w*.22,h*.22,w*.15),(.86,.56,.51,9.),f'air_sac:{index}')
                ring=[(cx+(x+.24*cos(tau*i/60))*(right-left),cy+(y+.23*sin(tau*i/60))*(bottom-top)) for i in range(61)]
                line(ring,.025,BLOOD,'capillary',z=.03)
            line([(cx,top),(cx,cy)],.06,MUCOSA,'bronchiole',z=-.08)
    elif kind=='villus':
        solid('sphere',(cx,cy),(w*.40,h*.46,w*.26),(.87,.53,.43,9.),'epithelium')
        route=[(cx-(right-left)*.19,bottom),(cx-(right-left)*.19,cy),(cx,top+(bottom-top)*.13),
               (cx+(right-left)*.19,cy),(cx+(right-left)*.19,bottom)]
        line(rounded_route(route),.025,BLOOD,'capillary')
        line([(cx,bottom),(cx,top+(bottom-top)*.28)],.018,(.72,.77,.48,.06),'lacteal')
        for angle in np.linspace(0,tau,18,endpoint=False):
            x=cx+cos(angle)*(right-left)*.40;y=cy+sin(angle)*(bottom-top)*.43
            line([(x,y),(x+cos(angle)*(right-left)*.055,y+sin(angle)*(bottom-top)*.035)],.008,MUCOSA,'microvilli',z=.025)
    elif kind in ('cell','food_bolus'):
        solid('sphere',(cx,cy),(w*.48,h*.46,min(w,h)*.30),(.52,.68,.65,8.) if kind=='cell' else (.77,.58,.37,.06),'cell_wall' if kind=='cell' else 'bolus')
        if kind=='cell':
            solid('sphere',(cx-(right-left)*.10,cy),(w*.14,h*.18,w*.12),(.36,.24,.49,.05),'nucleus',z=-.015)
            for x,y in ((.23,.11),(-.24,-.22),(.14,-.25)):
                solid('sphere',(cx+x*(right-left),cy+y*(bottom-top)),(w*.08,h*.04,w*.045),(.76,.40,.27,.06),'mitochondrion')
    elif kind=='red_blood_cell':
        solid('bio-rbc',(cx,cy),(w*.48,h*.48,min(w,h)*.62),BLOOD)
    elif kind=='membrane':
        for x in np.linspace(left,right,22):
            for sign in (-1,1):
                y=cy+sign*(bottom-top)*.32
                solid('sphere',(x,y),(w*.019,h*.17,.022),(.66,.75,.61,.04),'lipid_head')
                line([(x,y),(x+.2,cy+sign*(bottom-top)*.04)],.005,(.75,.61,.37,.04),'lipid_tail')
    elif kind=='receptor':
        line([(cx,bottom),(cx,cy),(left,top),(left+(right-left)*.22,top+(bottom-top)*.12)],.047,(.55,.35,.70,.05),'protein',z=.29)
        line([(cx,cy),(right,top),(right-(right-left)*.22,top+(bottom-top)*.12)],.047,(.55,.35,.70,.05),'protein',z=.29)
    elif kind=='neuron':
        solid('sphere',(cx,cy),(w*.13,h*.17,w*.07),(.66,.55,.75,.03),'soma')
        line([(cx,cy),(cx+(right-left)*.22,cy),(right,cy)],.02,(.82,.70,.38,.04),'axon')
        for sign in (-1,1):
            for amount in (.16,.32):
                line([(cx,cy),(cx-(right-left)*.23,cy+sign*(bottom-top)*amount),
                      (left,cy+sign*(bottom-top)*(amount+.10))],.013,(.66,.55,.75,.03),'dendrite')
    elif kind=='torso':
        organ([(-.12,.5),(.12,.5),(.18,.40),(.42,.34),(.48,.15),(.32,.04),(.28,-.22),
               (.34,-.48),(-.34,-.48),(-.28,-.22),(-.32,.04),(-.48,.15),(-.42,.34),(-.18,.40)],
              (.21,.30,.34,.06),depth=w*.16)
        # Keep the anatomy in front of the torso's back wall.
        for index,(vertices,color,role) in enumerate(out):
            vertices=vertices.copy();vertices[:,2]-=.40
            out[index]=(vertices,color,role)
    elif kind=='head':
        organ([(-.30,.43),(.03,.49),(.28,.36),(.32,.19),(.50,.03),(.33,-.06),
               (.38,-.16),(.29,-.36),(.08,-.45),(.04,-.5),(-.15,-.5),(-.18,-.24),(-.38,.02)],
              (.63,.42,.34,.04),depth=w*.19)
        solid('sphere',(cx+(right-left)*.18,cy-(bottom-top)*.14),(w*.035,h*.025,.015),(.19,.13,.12,.03),'eye',z=.04)
    elif kind=='mouth':
        solid('sphere',(cx,cy),(w*.46,h*.35,.040),(.26,.075,.085,.03),'oral_cavity',z=.015)
        solid('sphere',(cx,cy+(bottom-top)*.16),(w*.39,h*.12,.055),(.82,.34,.36,.03),'tongue',z=.04)
        line([(left,cy),(left+(right-left)*.15,bottom),(left+(right-left)*.30,bottom)],.028,MUCOSA,'pharynx')
    return out
