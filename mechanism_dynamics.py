# SPDX-License-Identifier: MIT
"""Continuous component states and circuit connectivity for generated scenes."""
from bisect import bisect_right


def eased(value):
    p=min(1.,max(0.,value))
    return p*p*(3-2*p)


class CurrentTrack:
    """Integrate signed current so particles slow down without jumping backwards."""
    def __init__(self,events,durations,effect='current'):
        offsets=[0.]
        for duration in durations:offsets.append(offsets[-1]+duration)
        self.segments=[];self.starts=[]
        for event in sorted(events,key=lambda a:(a.beat,a.start,a.end)):
            if event.effect!=effect:continue
            start=offsets[event.beat]+event.start*durations[event.beat]
            end=offsets[event.beat]+event.end*durations[event.beat]
            value=self.level(start);area=self.area(start)
            # An open contact stops current immediately. Other changes ramp.
            duration=end-start if event.amount[0] else 0.
            self.segments.append((start,duration,value,event.amount[0],area))
            self.starts.append(start)

    def _segment(self,time):
        i=bisect_right(self.starts,time)-1
        return self.segments[i] if i>=0 else None

    def level(self,time):
        segment=self._segment(time)
        if segment is None:return 0.
        start,duration,initial,target,_=segment
        return initial+(target-initial)*eased((time-start)/duration) if duration else target

    def area(self,time):
        segment=self._segment(time)
        if segment is None:return 0.
        start,duration,initial,target,area=segment
        dt=max(0.,time-start)
        if not duration:return area+target*dt
        p=min(1.,dt/duration)
        return area+initial*min(dt,duration)+(target-initial)*duration*(p**3-.5*p**4)+target*max(0.,dt-duration)


def conducting_wires(parts,closed):
    """Find wires on a closed source path, without treating an open branch as live.

    Capacitor terminal connectivity denotes the external charging circuit;
    particles still travel ONLY on wires, never across its dielectric.
    This checks topology, not voltages or a general circuit simulation.
    """
    graph={};sources=[]
    def edge(a,b,wire=None):
        graph.setdefault(a,[]).append((b,wire));graph.setdefault(b,[]).append((a,wire))
    for part in parts:
        name=part.part.label.casefold()
        if part.shape=='wire' and part.links:
            (a,pa),(b,pb)=part.links
            edge((a.casefold(),pa),(b.casefold(),pb),part.part.label)
        elif part.shape=='battery' or getattr(part,'electrical_role','')=='source':
            sources.append(((name,'positive' if part.shape=='battery' else 'left'),(name,'negative' if part.shape=='battery' else 'right')))
        elif part.shape=='switch':
            if closed.get(name,False):edge((name,'left'),(name,'right'))
        elif getattr(part,'electrical_role','') in ('load','conductor') or part.shape in ('resistor','capacitor','coil','motor','bulb','led','terminal','relay'):
            edge((name,'left'),(name,'right'))
    live=set();visited_count=0
    for start,goal in sources:
        def visit(node,seen,path):
            nonlocal visited_count
            visited_count+=1
            if visited_count>20000:
                return
            if node==goal:
                live.update(wire for wire in path if wire)
                return
            for following,wire in graph.get(node,()):
                if following not in seen:
                    visit(following,seen|{following},[*path,wire])
        visit(start,{start},[])
    return live


def series_wire_directions(parts):
    """Return orientations only for an unambiguous, single-source series loop."""
    sources=[p for p in parts if p.shape=='battery' or getattr(p,'electrical_role','')=='source']
    if len(sources)!=1:return {}
    graph={};wires=set()
    def edge(a,b,wire=None):
        graph.setdefault(a,[]).append((b,wire,1))
        graph.setdefault(b,[]).append((a,wire,-1))
    for part in parts:
        name=part.part.label.casefold()
        if part.shape=='wire':
            if len(part.links)!=2:return {}
            (a,pa),(b,pb)=part.links
            edge((a.casefold(),pa),(b.casefold(),pb),part.part.label)
            wires.add(part.part.label)
        elif getattr(part,'electrical_role','') in ('load','conductor') or part.shape in ('resistor','capacitor','coil','motor','bulb','led','terminal','switch'):
            edge((name,'left'),(name,'right'))
    name=sources[0].part.label.casefold()
    node=(name,'positive' if sources[0].shape=='battery' else 'left');goal=(name,'negative' if sources[0].shape=='battery' else 'right');seen=set();result={}
    while node!=goal:
        seen.add(node)
        following=[item for item in graph.get(node,()) if item[0] not in seen]
        if len(following)!=1:return {}
        node,wire,direction=following[0]
        if wire:result[wire]=direction
    if len(graph.get(goal,()))!=1 or set(result)!=wires:return {}
    return result
