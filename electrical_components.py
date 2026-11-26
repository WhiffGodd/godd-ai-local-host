# SPDX-License-Identifier: MIT
"""Reusable solid electrical parts, exposed contacts and cutaway internals.

Coordinates use the planner's board. Battery ports are top/bottom centre;
other parts have left/right centre ports. Animation is qualitative, not SPICE.
"""
from math import cos, sin, tau, pi

import numpy as np

from cinematic_geometry import mesh, scale, translate
from electrical_detail import printed, revolved, rounded_route, route_slice, smooth_profile

COPPER = (.84,.37,.15,.80)
CHROME = (.67,.73,.77,.85)
INSULATOR = (.08,.13,.20,.12)
CERAMIC = (.88,.83,.67,.15)
BLACK = (.035,.045,.055,.08)
BLUE_SLEEVE = (.035,.12,.30,.18)
INK = (.90,.92,.88,.03)


def electrical_meshes(component, world, wire):
    left,top = np.min(component.points,axis=0)
    right,bottom = np.max(component.points,axis=0)
    cx,cy = (left+right)/2,(top+bottom)/2
    width,height = right-left,bottom-top
    result = []

    def primitive(name, center, dimensions, material, role="body", z=0.):
        matrix = translate(*world(center,z))@scale(*dimensions)
        vertices = np.asarray(mesh(name),dtype=np.float32).copy()
        vertices[:,:3] = vertices[:,:3]@matrix[:3,:3].T+matrix[:3,3]
        vertices[:,3:] = vertices[:,3:]@np.linalg.inv(matrix[:3,:3])
        vertices[:,3:] /= np.linalg.norm(vertices[:,3:],axis=1,keepdims=True)
        result.append((vertices,material,role))

    def route(points, radius=.026, material=COPPER, role="body"):
        result.append((wire([world(point) for point in points],radius),material,role))

    def lathe(profile, center, material, role='body', axis='y', start=0., end=tau):
        vertices=revolved(profile,(0,0,0),start,end)
        if axis=='x':
            vertices=vertices[:,[1,0,2,4,3,5]].copy()
            vertices[:,1]*=-1
            vertices[:,4]*=-1
        vertices[:,:3]+=world(center)
        result.append((vertices,material,role))

    def label(text, center, width, height, radius, material=INK):
        result.append((printed(text,world(center),width,height,radius+.0015),material,'shell_print'))

    def shell(profile,center,material):
        lathe(profile,center,material,'shell_front',start=-pi/3,end=pi/3)
        lathe(profile,center,material,'shell',start=pi/3,end=5*pi/3)

    u = np.linalg.norm(world((1,0))-world((0,0)))
    shape = component.shape
    if shape == 'wire':
        path=np.array([world(point) for point in rounded_route(component.points)])
        total=np.linalg.norm(np.diff(path,axis=0),axis=1).sum()
        stripped=min(2.5*u/total,.18)
        lowered=component.part.label.casefold()
        jacket = (.055,.065,.085,.08) if any(word in lowered for word in ('return','negative','ground')) else (.60,.035,.025,.10)
        if 'coil' in lowered or 'control' in lowered:
            jacket=(.025,.18,.43,.12)
        result.append((wire(path,.027),COPPER,'conductor'))
        result.append((wire(route_slice(path,stripped,1-stripped),.061),jacket,'insulation'))
        strands=[]
        for a,b in ((0,stripped),(1-stripped,1)):
            exposed=route_slice(path,a,b)
            tangent=exposed[-1]-exposed[0]
            tangent/=max(np.linalg.norm(tangent),1e-8)
            side=np.cross(tangent,(0,0,1.))
            side/=max(np.linalg.norm(side),1e-8)
            for index in range(7):
                angle=tau*index/7
                strands.append(wire(exposed+.017*(side*cos(angle)+np.array((0,0,1))*sin(angle)),.006))
        result.append((np.concatenate(strands),(.95,.51,.23,.80),'copper_strands'))
        for a,b in ((stripped*.7,stripped*.96),(1-stripped*.96,1-stripped*.7)):
            result.append((wire(route_slice(path,a,b),.034),CHROME,'ferrule'))
    elif shape == "battery":
        radius=width*u*.45
        h=height*u
        # An AA-style metal cell: rolled sleeve, crimped rim, button and flat end.
        shell([(-h*.46,radius*.97),(-h*.44,radius),(h*.08,radius)],(cx,cy),BLACK)
        shell([(h*.08,radius),(h*.42,radius),(h*.46,radius*.94)],(cx,cy),COPPER)
        for y in (-h*.46,h*.46):
            lathe([(y-.009,0),(y-.009,radius*.96),(y+.009,radius*.96),(y+.009,0)],(cx,cy),CHROME,'end_cap')
        lathe([(h*.465,0),(h*.465,radius*.45),(h*.485,radius*.45),(h*.50,radius*.29),(h*.50,0)],(cx,cy),CHROME,'positive_terminal')
        lathe([(-h*.50,0),(-h*.50,radius*.55),(-h*.46,radius*.55),(-h*.46,0)],(cx,cy),CHROME,'negative_terminal')
        lathe([(h*.46,radius*.43),(h*.46,radius*.68),(h*.465,radius*.68),(h*.465,radius*.43)],(cx,cy),BLACK,'gasket')
        label('+',(cx,top+height*.22),radius*.65,h*.09,radius)
        label('DC CELL',(cx,cy+height*.04),radius*1.30,h*.055,radius)
        label('ALKALINE',(cx,cy+height*.14),radius*1.30,h*.042,radius)
        label('-',(cx,bottom-height*.16),radius*.6,h*.04,radius)
        # Nested, offset cutaways reveal the cathode, separator and collector.
        for r,material in ((radius*.87,(.18,.19,.20,.2)),(radius*.61,(.80,.78,.64,.03)),(radius*.54,(.43,.46,.47,.55))):
            lathe([(-h*.42,r),(h*.42,r)],(cx,cy),material,'internal',start=pi/6,end=11*pi/6)
        lathe([(-h*.40,0),(-h*.40,radius*.15),(h*.40,radius*.15),(h*.40,0)],(cx,cy),CHROME,'internal')
    elif shape == "bulb":
        w,h=width*u,height*u
        lathe(smooth_profile([(-h*.29,w*.18),(-h*.20,w*.22),(-h*.08,w*.36),(h*.12,w*.44),
               (h*.30,w*.34),(h*.43,w*.15),(h*.45,0)]),(cx,cy),(.58,.76,.90,8.),'glass')
        lathe([(-h*.48,0),(-h*.48,w*.16),(-h*.28,w*.23),(-h*.23,w*.22),(-h*.23,0)],(cx,cy),CHROME,'screw_base')
        thread=[world((cx,cy+height*(.27+.19*i/160)))+
                np.array((w*.235*cos(tau*5*i/160),0,w*.235*sin(tau*5*i/160))) for i in range(161)]
        result.append((wire(thread,.012),CHROME,'screw_thread'))
        lathe([(-h*.50,0),(-h*.50,w*.12),(-h*.48,w*.12),(-h*.48,0)],(cx,cy),BLACK,'base_insulator')
        route([(left,cy),(cx-width*.19,cy),(cx-width*.19,cy-height*.12)],.022,CHROME)
        route([(cx+width*.19,cy-height*.12),(cx+width*.19,cy),(right,cy)],.022,CHROME)
        filament = [(cx-width*.19+width*.38*i/60,cy-height*.12+height*.04*sin(tau*5*i/60)) for i in range(61)]
        route(filament,.016,(.33,.24,.12,.55),"filament")
    elif shape == 'led':
        w,h=width*u,height*u
        dome=[(h*(.13+.29*sin(angle)),w*.33*cos(angle)) for angle in np.linspace(0,pi/2,30)]
        lathe([(-h*.17,0),(-h*.17,w*.33),*dome],(cx,cy),(.92,.12,.075,8.),'glass')
        lathe([(-h*.21,0),(-h*.21,w*.39),(-h*.16,w*.39),(-h*.16,0)],(cx,cy),(.55,.06,.04,.15),'rim')
        for sign,endpoint in ((-1,left),(1,right)):
            route([(endpoint,cy),(endpoint,cy+height*.42),(cx+sign*width*.12,cy+height*.42),(cx+sign*width*.12,cy-height*.06)],.023,CHROME)
        primitive('beveled-box',(cx,cy-height*.05),(w*.13,h*.06,.025),(.7,.12,.06,.10),'filament',z=.04)
    elif shape == "resistor":
        length,radius=width*u*.60,min(height*.36,width*.18)*u
        lathe([(-length*.5,0),(-length*.5,radius*.65),(-length*.43,radius),(length*.43,radius),(length*.5,radius*.65),(length*.5,0)],(cx,cy),CERAMIC,axis='x')
        for position,color in ((-.28,(.25,.075,.025,.08)),(-.11,BLACK),(.08,(.62,.025,.015,.08)),(.32,(.77,.56,.17,.65))):
            p=position*length
            lathe([(p-length*.028,radius*1.012),(p+length*.028,radius*1.012)],(cx,cy),color,'color_band',axis='x')
        route([(left,cy),(cx-width*.3,cy)],.025,CHROME)
        route([(cx+width*.3,cy),(right,cy)],.025,CHROME)
    elif shape == "capacitor":
        radius=min(width*.30,height*.27)*u
        h=height*u*.64
        center=(cx,cy-height*.12)
        shell([(-h*.5,radius*.93),(-h*.45,radius),(h*.45,radius),(h*.5,radius*.93)],center,BLUE_SLEEVE)
        lathe([(h*.49,0),(h*.49,radius*.92),(h*.51,radius*.92),(h*.51,0)],center,CHROME,'can_top')
        lathe([(-h*.53,0),(-h*.53,radius*.86),(-h*.49,radius*.86),(-h*.49,0)],center,BLACK,'rubber_bung')
        for level in (-.47,.47):
            lathe([(h*level-.008,radius*.98),(h*level+.008,radius*.98)],center,CHROME,'crimp')
        # Scored pressure-relief vent on the top aluminium disc.
        for angle in (pi/4,-pi/4):
            mid=world(center)+np.array((0,h*.514,0))
            vector=np.array((cos(angle),0,sin(angle)))*radius*.64
            result.append((wire([mid-vector,mid+vector],.005),BLACK,'safety_vent'))
        label('CAP',(cx,cy-height*.22),radius*1.15,h*.11,radius)
        label('ELECTROLYTIC',(cx,cy-height*.10),radius*1.45,h*.067,radius)
        # Polarity stripe is printed on the right side of the sleeve.
        strip=revolved([(-h*.42,radius+.001),(h*.42,radius+.001)],world(center),.48,.83,12)
        result.append((strip,INK,'shell_print'))
        for y in (-.30,0,.30):
            mark=printed('-',world((cx,center[1]-h*y/u)),radius*.27,h*.07,radius+.002)
            # Shift markings around the can to match the polarity stripe.
            angle=.65
            c=world((cx,center[1]-h*y/u))
            p=mark[:,:3]-c
            mark[:,:3]=p@np.array(((cos(angle),0,-sin(angle)),(0,1,0),(sin(angle),0,cos(angle))))+c
            n=mark[:,3:].copy()
            mark[:,3:]=n@np.array(((cos(angle),0,-sin(angle)),(0,1,0),(sin(angle),0,cos(angle))))
            result.append((mark,BLACK,'shell_print'))
        for sign,port in ((-1,left),(1,right)):
            x=cx+sign*width*.13
            route([(x,cy+height*.20),(x,cy+height*.43),(port+(-sign)*width*.04,cy+height*.43),
                   (port+(-sign)*width*.04,cy),(port,cy)],.025,CHROME,'lead')
        # A rolled foil/dielectric assembly, visible when a detail view opens the sleeve.
        for material,offset in ((CHROME,0),(CERAMIC,.009)):
            vertices=[]
            for index in range(600):
                upper = h*.02 if cos(tau*8*(index+.5)/600)>.30 else h*.42
                for step,y in ((index,-h*.42),(index,upper),(index+1,upper),
                               (index,-h*.42),(index+1,upper),(index+1,-h*.42)):
                    angle=tau*8*step/600
                    r=radius*(.13+.72*step/600)+offset
                    p=world(center)+np.array((r*sin(angle),y,r*cos(angle)))
                    vertices.append((*p,sin(angle),0,cos(angle)))
                for step,extra in ((index,0),(index,.006),(index+1,.006),(index,0),(index+1,.006),(index+1,0)):
                    angle=tau*8*step/600
                    r=radius*(.13+.72*step/600)+offset+extra
                    p=world(center)+np.array((r*sin(angle),upper,r*cos(angle)))
                    vertices.append((*p,0,1,0))
            result.append((np.asarray(vertices,dtype=np.float32),material,'internal'))
    elif shape in ("coil","relay"):
        r=height*u*.30
        length=width*u*.78
        lathe([(-length*.5,0),(-length*.5,r*.42),(length*.5,r*.42),(length*.5,0)],(cx,cy),CHROME,'core',axis='x')
        for side in (-1,1):
            position=side*width*u*.34
            lathe([(position-.015,0),(position-.015,r*1.16),(position+.015,r*1.16),(position+.015,0)],(cx,cy),BLACK,'bobbin',axis='x')
        coil = [world((cx-width*.32+width*.64*i/160,cy))+
                np.array((0,height*u*.30*cos(tau*8*i/160),height*u*.30*sin(tau*8*i/160))) for i in range(161)]
        result.append((wire(coil,.020),COPPER,"winding"))
        route([(left,cy),(cx-width*.32,cy)],.025)
        route([(cx+width*.32,cy),(right,cy)],.025)
        for expansion in (1.,1.35):
            field = [(cx+width*.48*expansion*cos(tau*i/80),cy+height*.55*expansion*sin(tau*i/80)) for i in range(81)]
            route(field,.007,(.15,.60,.95,7.),"field")
        if shape == "relay":
            primitive("box",(cx,top+height*.08),(width*u*.8,height*u*.08,.13),CHROME,"armature")
    elif shape == "motor":
        # Open-front motor housing, end plate and mounting screws stay fixed.
        # Separate copper coils, commutator and shaft rotate as one assembly.
        w,h=width*u,height*u
        radius=min(w,h)*.40
        primitive('ring',(cx,cy),(radius,radius,.30),CHROME,'stator',z=-.07)
        primitive('cylinder',(cx,cy),(radius*.95,radius*.95,.025),CHROME,'stator',z=-.22)
        for angle in (pi/4,3*pi/4,5*pi/4,7*pi/4):
            position=(cx+radius*.86*cos(angle)/u,cy+radius*.86*sin(angle)/u)
            primitive('recessed-bolt',position,(radius*.06,radius*.06,.03),CHROME,'stator',z=.10)
        for sign in (-1,1):
            primitive("beveled-box",(cx,cy+sign*radius*.68/u),(radius*.98,radius*.34,.19),(.65,.14,.10,.4) if sign<0 else (.10,.29,.63,.4),"stator")
            result.append((printed('N' if sign<0 else 'S',world((cx,cy+sign*radius*.68/u),.098),radius*.25,radius*.20),INK,'stator'))
        for angle in (0,tau/3,2*tau/3):
            center=world((cx,cy))
            radial=np.array((cos(angle),sin(angle),0.))
            side=np.array((-sin(angle),cos(angle),0.))
            turns=[]
            for turn in range(5):
                distance=radius*(.14+turn*.035)
                for t in np.linspace(0,1,60):
                    a=tau*t
                    turns.append(center+radial*(radius*.34+distance*cos(a))+side*(radius*.17*sin(a))+np.array((0,0,.02+turn*.012)))
            result.append((wire(turns,.012),COPPER,'rotor'))
        primitive('cylinder',(cx,cy),(.055,.055,.52),CHROME,'rotor',z=.05)
        primitive('cylinder',(cx,cy),(.11,.11,.09),COPPER,'rotor',z=.22)
        for sign in (-1,1):
            primitive('beveled-box',(cx+sign*.14/u,cy),(.07,.10,.075),BLACK,'stator',z=.22)
        route([(left,cy),(cx-width*.35,cy)],.025,CHROME)
        route([(cx+width*.35,cy),(right,cy)],.025,CHROME)
    elif shape == "switch":
        primitive("beveled-box",(cx,cy+height*.25),(width*u,height*u*.40,.13),CERAMIC)
        for x in (left,right):
            primitive('cylinder',(x,cy),(.063,.063,.14),CHROME,z=.01)
            primitive('beveled-box',(x,cy),(.08,.012,.005),BLACK,z=.084)
            primitive('beveled-box',(x,cy),(.012,.08,.005),BLACK,z=.084)
    elif shape == "terminal":
        primitive('cylinder',(cx,cy),(width*u*.45,height*u*.45,.11),CHROME)
        primitive('beveled-box',(cx,cy),(width*u*.65,height*u*.08,.004),BLACK,z=.058)
    return result
