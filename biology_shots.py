# SPDX-License-Identifier: MIT
"""Continuous transport, dissolving particles and gas transfer for biology scenes."""
from math import cos, sin, tan, tau

import numpy as np
from PIL import ImageDraw

from cinematic_geometry import scale, spin, translate
from cinematic_render import _font, _look_at, _perspective
from mechanism_3d import Mechanism3DShot
from mechanism_animation import biological_level, motion_state


def _ease(value):
    p=min(1.,max(0.,value))
    return p*p*(3-2*p)


def _along(points,fraction):
    points=np.asarray(points,dtype=float)
    lengths=np.linalg.norm(np.diff(points,axis=0),axis=1)
    remaining=min(1.,max(0.,fraction))*sum(lengths)
    for a,b,length in zip(points,points[1:],lengths):
        if length and remaining<=length:
            return a+(b-a)*remaining/length
        remaining-=length
    return points[-1]


class BiologyShot(Mechanism3DShot):
    subject='biology'
    topic=''

    def fraction(self,time):
        return min(1.,max(0.,time/max(self.duration-1/30,.01)))

    def _camera(self,box):
        left,top,right,bottom=box
        focus=self.model.world(((left+right)/2,(top+bottom)/2),.02)
        aspect=self.size[0]/self.size[1]
        distance=max((bottom-top)/2,(right-left)/2/aspect)*self.model.unit/tan(.78/2)*1.16
        eye=focus+np.array((distance*.025,distance*.065,distance))
        self.camera=eye,focus
        return eye,focus

    def _marker(self,objects,point,color=(1.,.66,.17,7.),radius=.030,group=''):
        objects.append(('bio-marker',color,translate(*point)@scale(radius,radius,radius),group))

    def _blood(self,objects,route,clock,count=9,matrix=None,bound_oxygen=False):
        for index in range(count):
            f=(clock*.12+index/count)%1
            point=_along(route,f)
            transform=translate(*point)@spin(.35*sin(clock+index))@scale(.053,.041,.037)
            if matrix is not None:
                transform=matrix@transform
            color=(.56+.18*f,.035+.015*f,.07,.06)
            objects.append(('bio-rbc',color,transform,''))
            if bound_oxygen:
                for side in (-1,1):
                    p=point+np.array((side*.018,.0,.035))
                    if matrix is not None:
                        p=(matrix@np.append(p,1))[:3]
                    self._marker(objects,p,(.20,.84,.96,7.),.010)

    def _label(self,draw,text,point,shift=(0,0),color='#d6e3e7'):
        width,height=self.size
        eye,focus=self.camera
        projection=_perspective(width/height,.78)@_look_at(eye,focus)
        p=projection@np.append(self.model.world(point,.20),1.)
        if p[3]<=0:
            return
        x,y=(p[:2]/p[3]*np.array((1,-1))+1)*np.array((width,height))/2
        x+=shift[0]*width;y+=shift[1]*height
        font=_font(round(width*.026))
        bounds=draw.textbbox((0,0),text,font=font)
        tw=bounds[2]-bounds[0]
        x=min(width-tw-10,max(10,x-tw/2))
        y=min(height*.82,max(height*.25,y))
        draw.rounded_rectangle((x-4,y-3,x+tw+4,y+width*.035),radius=4,fill='#111e27')
        draw.text((x,y),text,font=font,fill=color)

    def _header(self,frame,title,subtitle):
        w,h=self.size;draw=ImageDraw.Draw(frame)
        draw.text((w*.065,h*.075),title,font=_font(round(w*.034)),fill='#edf3e9')
        draw.text((w*.065,h*.20),subtitle,font=_font(round(w*.025)),fill='#e6c28c')
        draw.text((w*.065,h*.92),'EDUCATIONAL CUTAWAY - SCALE / TIME SIMPLIFIED',font=_font(round(w*.021)),fill='#98aeb8')
        return draw


class MedicineShot(BiologyShot):
    topic='oral-medicine'
    macro={'Torso','Head','Mouth','Esophagus','Stomach','Duodenum','Small intestine','Liver','Heart','Left kidney','Right kidney','Tablet'}

    def at(self,time,part=None):
        raw,_,_=super().at(time,part)
        p=self.fraction(time);clock=self.offset+time
        if self.beat in (0,1):
            allowed=self.macro;box=(5,0,95,103)
        elif self.beat==2:
            allowed={'Stomach','Tablet','Duodenum'};box=(39,32,81,66)
        elif self.beat==3:
            allowed={'Villus','Absorption capillary'};box=(4,28,36,75)
        elif self.beat==4:
            allowed={'Small intestine','Portal blood','Liver'};box=(15,30,77,91)
        elif self.beat==5:
            allowed={'Target cell','Cell membrane','Target receptor'};box=(5,28,51,85)
        else:
            allowed=(self.macro-{'Tablet','Head','Mouth','Esophagus','Stomach'})|{'Left ureter','Right ureter','Bladder'};box=(14,29,89,100)
        objects=[row for row in raw if row[3] in allowed and row[0] not in ('sphere','bio-rbc')]
        if self.beat<=1:
            fraction=0. if self.beat==0 else _ease((p-.05)/.85)
            point=_along(((65,12),(59,12),(55,18),(55,39)),fraction)
            pill_y=point[1]
            for index,row in enumerate(objects):
                name,material,matrix,group=row
                role=self.model.roles.get(name,'')
                if group=='Tablet':
                    matrix=translate(*self.model.world(point))@translate(*(-self.model.world((65,12))))
                    objects[index]=(name,material,matrix,group)
                if group=='Esophagus' and role.startswith('band:'):
                    y=19+20*int(role.split(':')[1])/26
                    radial=1-.38*np.exp(-((y-(pill_y-4))/2.7)**2)
                    center=self.model.world((55,y))
                    objects[index]=(name,material,translate(*center)@scale(radial,1,radial)@translate(*(-center))@matrix,group)
        if self.beat==2:
            # Preserve the intact tablet until breakup begins. Show particles
            # confined to digestive fluid; no solid pill crosses an epithelium.
            events=tuple(a for a in self.model.actions if a.part=='Tablet')
            dissolved=biological_level(events,'dissolve',self.beat,p)
            for index in range(round(24*dissolved)):
                angle=index*2.399+clock*.5
                r=1.5+2.8*((index*7)%19)/19
                point=self.model.world((62+r*cos(angle),47+r*.85*sin(angle)),.08)
                if p>.72 and index%3==0:
                    route=[self.model.world(v,.08) for v in ((62,47),(56,50),(50,50),(48,55),(43,55),(38,60),(37.46,61.97))]
                    point=_along(route,min(1.,(p-.72)/.28+(index%5)*.04))
                self._marker(objects,point,radius=.021)
        elif self.beat==3:
            route=[self.model.world(point,.12) for point in ((8,42),(13,44),(19,48),(19,61),(29,61))]
            for index in range(12):
                f=(clock*.13+index/12)%1
                self._marker(objects,_along(route,f),radius=.028)
            blood=[self.model.world(point,.05) for point in ((11,61),(29,61))]
            self._blood(objects,blood,clock,5)
        elif self.beat==4:
            route=self.model.routes['Portal blood']
            self._blood(objects,route,clock,9)
            for index in range(11):
                f=(clock*.11+index/11)%1
                # A different marker color indicates illustrative processing,
                # not a measured fraction or the molecular structure of a drug.
                color=(1.,.66,.17,7.) if f<.87 else (.34,.81,.77,7.)
                self._marker(objects,_along(route,f)+np.array((0,0,.03)),color,.023)
        elif self.beat==5:
            f=_ease(min(1.,p/.62))
            point=_along([self.model.world(v,.31) for v in ((14,32),(21,34),(28.5,41.6))],f)
            self._marker(objects,point,radius=.044)
            for delta in ((.025,0,0),(-.012,.022,0)):
                self._marker(objects,point+delta,radius=.025)
            if p>.62:
                for index,row in enumerate(objects):
                    name,material,matrix,group=row
                    if group=='Target receptor':
                        objects[index]=(name,(.73,.50,.25,.08),matrix,group)
                for index in range(4):
                    f=(clock*.16+index/4)%1
                    self._marker(objects,self.model.world((28.5,55+f*10),.13),(.38,.79,.69,7.),.018)
        elif self.beat>=6:
            for center,name in ((29,'Left ureter'),(80,'Right ureter')):
                route=[self.model.world((center,65),.10),*self.model.routes[name]]
                for index in range(6):
                    f=(clock*.13+index/6)%1
                    self._marker(objects,_along(route,f),(.34,.81,.77,7.),.021)
        eye,focus=self._camera(box)
        return objects,eye,focus

    def overlay(self,frame,time):
        subtitles=('SWALLOW','TRANSPORT','DISSOLVE','ABSORB','LIVER PASS','TARGET EXAMPLE','CLEARANCE')
        capsule=any(c.part.label=='Tablet' and c.shape=='capsule' for c in self.model.parts)
        draw=self._header(frame,'A CAPSULE\'S JOURNEY' if capsule else 'A TABLET\'S JOURNEY',subtitles[min(self.beat,6)]+'  /  DIFFERENT MEDICINES VARY')
        if self.beat<=1:
            self._label(draw,'ESOPHAGUS',(59,28),(.10,0))
            self._label(draw,'STOMACH',(72,44),(.05,0))
            self._label(draw,'SMALL INTESTINE',(50,85),(0,.015))
        elif self.beat==2:
            self._label(draw,'DISSOLVED MEDICINE MARKERS',(62,57),(0,.02), '#f2c875')
        elif self.beat==3:
            self._label(draw,'INTESTINAL VILLUS',(20,34),(0,-.025))
            self._label(draw,'CAPILLARY / BLOOD',(27,58),(.12,-.015),'#ef8e94')
        elif self.beat==4:
            self._label(draw,'LIVER',(37,37),(0,-.02))
            self._label(draw,'PORTAL BLOOD',(28,60),(-.03,0))
            self._label(draw,'SMALL INTESTINE',(51,84),(0,.02))
        elif self.beat==5:
            self._label(draw,'ILLUSTRATIVE PROTEIN BINDING',(28,34),(0,-.025))
            self._label(draw,'CELL MEMBRANE',(16,49),(-.10,-.04))
        else:
            self._label(draw,'LIVER PROCESSING',(36,42),(0,-.025))
            self._label(draw,'KIDNEY CLEARANCE',(51,79),(0,.03))


class PeristalsisShot(BiologyShot):
    topic='swallowing-peristalsis'

    def at(self,time,part=None):
        raw,_,_=super().at(time,part)
        p=self.fraction(time)
        food=next(c for c in self.model.parts if c.part.label=='Food bolus')
        events=tuple(a for a in self.model.actions if a.part=='Food bolus')
        dx,dy,*_=motion_state(events,self.beat,p)
        self.bolus=(food.pivot[0]+dx,food.pivot[1]+dy)
        objects=[]
        for name,material,matrix,group in raw:
            role=self.model.roles.get(name,'')
            if group=='Esophagus' and role.startswith('band:'):
                index=int(role.split(':')[1]);y=13+74*index/26
                contraction=.51*np.exp(-((y-(self.bolus[1]-8))/5.5)**2)
                radial=1-contraction
                if index>=25 and self.beat==5:
                    radial=1-.62*_ease((p-.6)/.4)
                center=self.model.world((50,y))
                matrix=translate(*center)@scale(radial,1,radial)@translate(*(-center))@matrix
            objects.append((name,material,matrix,group))
        box=(29,8,86,101) if self.beat<2 else (31,self.bolus[1]-40,86,self.bolus[1]+48)
        eye,focus=self._camera(box)
        return objects,eye,focus

    def overlay(self,frame,time):
        draw=self._header(frame,'HOW PERISTALSIS MOVES FOOD','MUSCLE WAVE  /  ESOPHAGUS CUTAWAY')
        self._label(draw,'FOOD BOLUS',self.bolus,(.15,-.04))
        self._label(draw,'CONTRACTION BEHIND FOOD',(50,self.bolus[1]-8),(-.17,-.015),'#efb0a2')
        self._label(draw,'LOWER SPHINCTER',(50,87),(-.15,.02))


class GasExchangeShot(BiologyShot):
    topic='alveolar-gas-exchange'

    def at(self,time,part=None):
        raw,_,_=super().at(time,part)
        clock=self.offset+time
        if self.beat<=1:
            allowed={'Lungs'};box=(12,5,88,49)
        else:
            allowed={'Alveoli','Blood capillary'};box=(22,40,77,89)
        objects=[row for row in raw if row[3] in allowed and row[0] not in ('sphere','bio-rbc')]
        if self.beat>=2:
            matrix=next(row[2] for row in objects if row[3]=='Alveoli')
            ring=[self.model.world((38.22+11.28*cos(tau*i/60),68.04+8.74*sin(tau*i/60)),.08) for i in range(61)]
            self._blood(objects,ring,clock,8,matrix,self.beat>=3)
            for gas,direction,color in (('OXYGEN',1,(.19,.84,.97,7.)),('CARBON DIOXIDE',-1,(1.,.62,.16,7.))):
                route=[self.model.world(v,.11) for v in ((38,66),(38,62),(38,59.3))]
                if direction<0:
                    route=list(reversed(route))
                    if self.beat==5:
                        route += [self.model.world(v,.11) for v in ((49.5,58),(49.5,46))]
                for index in range(6):
                    f=(clock*.18+index/6)%1
                    point=(matrix@np.append(_along(route,f),1.))[:3]
                    radius=.022 if (direction>0 and self.beat in (2,3) or direction<0 and self.beat in (4,5)) else .016
                    self._marker(objects,point,color,radius)
                    self._marker(objects,point+np.array((radius*1.4,0,0)),color,radius*.8)
        eye,focus=self._camera(box)
        return objects,eye,focus

    def overlay(self,frame,time):
        draw=self._header(frame,'LUNGS: AIR TO BLOOD','CYAN: OXYGEN  /  AMBER: CARBON DIOXIDE')
        if self.beat<=1:
            self._label(draw,'BRANCHING AIRWAYS',(50,14),(0,-.015))
            self._label(draw,'LUNGS',(50,40),(0,.025))
        else:
            self._label(draw,'ALVEOLAR AIR',(38,67),(-.06,0))
            self._label(draw,'THIN AIR-BLOOD BARRIER',(38,59),(-.02,-.04))
            self._label(draw,'RED BLOOD CELLS',(43,77),(.07,.02),'#ef8e94')


BIOLOGY_SHOTS={'oral-medicine':MedicineShot,'swallowing-peristalsis':PeristalsisShot,'alveolar-gas-exchange':GasExchangeShot}
