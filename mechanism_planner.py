# SPDX-License-Identifier: MIT
"""Bounded, staged planning shared by every custom 3D mechanism."""
import copy
import json
import re

import requests

from biological_components import BIOLOGICAL_SHAPES
from mechanism_animation import ELECTRICAL_SHAPES, PALETTE, SHAPES, _electrical_shape, mechanism_schema, parse_mechanism_rows, read_mechanism
from planning_json import planning_json
from mechanism_dynamics import conducting_wires, series_wire_directions


def _key(name):
    return ' '.join(name.replace('_',' ').split()).casefold()


def electrical_ports(part):
    x,y=zip(*part['points'])
    l,t,r,b=min(x),min(y),max(x),max(y)
    if part['shape']=='battery':
        return {'positive':[(l+r)/2,t],'negative':[(l+r)/2,b]}
    if part['shape'] in ELECTRICAL_SHAPES and part['shape']!='wire':
        return {'left':[l,(t+b)/2],'right':[r,(t+b)/2]}
    return {}


def _parts_data(data,beats):
    """Canonicalize geometry without inventing any animation actions."""
    data=copy.deepcopy(data)
    flat=[]
    for item in data['parts']:
        if not isinstance(item,dict):continue
        points=item.get('points',[])
        shape=item.get('shape')
        # A plate drawn edge-on is a thin solid, not an impossible zero-area mesh.
        # Keep its centreline and give only that missing dimension a two-unit width.
        # Never invent the dimensions of gears, anatomy or manufactured components.
        if (shape=='plate' and _electrical_shape(item.get('name',''),shape)=='plate'
                and isinstance(points,list) and len(points)==2
                and all(isinstance(p,list) and len(p)==2 and all(type(x) in (int,float) for x in p) for p in points)
                and points[0]!=points[1]):
            for axis in (0,1):
                if points[0][axis]==points[1][axis] and 0<=points[0][axis]<=100:
                    centre=points[0][axis]
                    lo=max(0,min(98,centre-1))
                    points[0][axis],points[1][axis]=lo,lo+2
        filled=shape in ('plate','oval','gear') or shape in ELECTRICAL_SHAPES and shape!='wire' or shape in BIOLOGICAL_SHAPES and shape not in ('blood_vessel','ureter','digestive_tube')
        if (filled and isinstance(points,list) and len(points)>=2
                and all(isinstance(p,list) and len(p)==2 and all(type(x) in (int,float) for x in p) for p in points)
                and any(len(set(axis))<2 for axis in zip(*points))):
            flat.append(f"{item.get('name')} ({shape}): {points}")
    if flat:
        raise ValueError('All these filled parts need BOTH width and height: '+'; '.join(flat)+
                         '. Change BOTH x and y between opposite corners. Thin base example: [[10,70],[90,74]]. Do not leave any flat filled parts')
    parts,_=parse_mechanism_rows({'parts':data['parts'],'actions':[]},beats,require_animation=False)
    source={_key(p['name']):p for p in data['parts']} if isinstance(data['parts'][0],dict) else {}
    entries=[]
    for p in parts:
        color=next(key for key,value in PALETTE.items() if value==p.color)
        entries.append({'name':p.part.label,'shape':p.shape,'color':color,'pivot':list(p.pivot),
                        'points':[list(point) for point in p.points],
                        'links':source.get(_key(p.part.label),{}).get('links',[])})
    by_name={_key(p['name']):p for p in entries}
    for part in entries:
        links=part['links']
        if not links:
            if (part['shape']=='wire' and source and 'links' in source[_key(part['name'])]
                    and any(p['shape']=='battery' for p in entries)):
                raise ValueError(f"{part['name']}: electrical wires need two terminal links")
            continue
        if part['shape']!='wire' or not isinstance(links,list) or len(links)!=2:
            raise ValueError(f"{part['name']}: wire links must name exactly two terminals")
        endpoints=[];canonical=[]
        for link in links:
            if not isinstance(link,str) or ':' not in link:
                raise ValueError(f"{part['name']}: use a terminal link like Battery:positive")
            name,port=link.rsplit(':',1)
            target=by_name.get(_key(name))
            if target is None:
                raise ValueError(f"{part['name']}: linked part {name!r} does not exist")
            ports=electrical_ports(target)
            port={'+':'positive','-':'negative','pos':'positive','neg':'negative'}.get(port.strip().casefold(),port.strip().casefold())
            if port not in ports:
                raise ValueError(f"{part['name']}: {target['name']} has terminals {', '.join(ports)}, not {port}")
            endpoints.append(ports[port]);canonical.append([target['name'],port])
        part['points'][0],part['points'][-1]=endpoints
        part['pivot']=endpoints[0]
        part['links']=canonical
    validated,_=read_mechanism({'parts':entries,'actions':[]},beats,require_animation=False)
    if any(p.shape=='battery' for p in validated) and any('links' in p for p in source.values()):
        wires={p.part.label for p in validated if p.shape=='wire'}
        live=conducting_wires(validated,{p.part.label.casefold():True for p in validated if p.shape=='switch'})
        if not wires or wires-live:
            raise ValueError('Battery circuit is incomplete: add connected wires from battery positive through the components back to negative; every wire must belong to a complete path')
    return entries


def _plain_parts(parts):
    return [{k:v for k,v in part.items() if k!='links' or v} for part in parts]


def _finish_actions(parts,actions,beats):
    components,_=read_mechanism({'parts':parts,'actions':[]},beats,require_animation=False)
    directions=series_wire_directions(components)
    if directions:
        # Kirchhoff continuity in a verified series loop: infer no branch currents.
        groups={};other=[]
        for item in actions:
            if item.get('effect')!='current' or item.get('part') not in directions:
                other.append(item);continue
            identity=(item['beat'],item['start'],item['end'])
            value=item['amount'][0]*directions[item['part']]
            if identity in groups and abs(groups[identity]-value)>1e-6:
                raise ValueError('Conflicting currents in a series circuit: every series wire carries the same current, with sign adjusted for its route direction')
            groups[identity]=value
        actions=other+[dict(beat=beat,start=start,end=end,part=name,effect='current',amount=[value*direction,0])
            for (beat,start,end),value in groups.items() for name,direction in directions.items()]
    return read_mechanism({'parts':parts,'actions':actions},beats)


def _domain(text):
    electrical=bool(re.search(r'\b(?:batter\w*|capacit\w*|resistor\w*|circuit\w*|wire\w*|electr\w*|coil\w*|solenoid\w*|motor\w*|relay\w*|voltage)\b',text,re.I))
    biology=bool(re.search(r'\b(?:neuron\w*|villus|villi|pill\w*|liver|biolog\w*|blood|kidney\w*|lung\w*|stomach|membrane\w*|digest\w*)\b',text,re.I))
    shapes=[shape for shape in SHAPES if shape not in (*ELECTRICAL_SHAPES,*BIOLOGICAL_SHAPES)]
    if electrical:shapes.extend(ELECTRICAL_SHAPES)
    if biology:shapes.extend(BIOLOGICAL_SHAPES)
    return list(dict.fromkeys(shapes)),electrical,biology


def parts_schema(beats,shapes):
    part=copy.deepcopy(mechanism_schema(beats)['properties']['parts']['items'])
    part['properties']['shape']['enum']=shapes
    part['properties']['links']={'type':'array','maxItems':2,'items':{'type':'string'},
        'description':'For a wire only: ["Battery:positive","Switch:left"]. Other parts: [].'}
    part['required'].append('links')
    # Disjoint alternatives prevent a solid component from acquiring wire links.
    solid=copy.deepcopy(part)
    solid['properties']['shape']['enum']=[s for s in shapes if s!='wire']
    solid['properties']['links']['maxItems']=0
    variants=[solid]
    if 'wire' in shapes:
        wire=copy.deepcopy(part)
        wire['properties']['shape']={'type':'string','const':'wire'}
        wire['properties']['links']['minItems']=2
        variants.append(wire)
    return {'type':'object','properties':{'parts':{'type':'array','minItems':1,'maxItems':24,'items':{'anyOf':variants}}},'required':['parts']}


def allowed_effects(shape):
    effects=['move','turn','expand','energize']
    if shape=='switch':effects.remove('turn');effects.append('switch')
    if shape=='capacitor':effects.append('charge')
    if shape in ('pipe','path','wire','blood_vessel','esophagus','intestine','neuron','ureter','digestive_tube'):
        effects.append('flow')
    if shape in ('pipe','path','wire'):effects.append('current')
    if shape in BIOLOGICAL_SHAPES:effects.append('pulse')
    if shape in ('tablet','capsule'):effects.append('dissolve')
    return effects


def actions_schema(beats,parts):
    variants=[]
    for part in parts:
        action=copy.deepcopy(mechanism_schema(beats)['properties']['actions']['items'])
        action['properties']['part']={'type':'string','const':part['name']}
        action['properties']['effect']={'type':'string','enum':allowed_effects(part['shape'])}
        variants.append(action)
    return {'type':'object','properties':{'actions':{'type':'array','minItems':1,'maxItems':64,'items':{'anyOf':variants}}},'required':['actions']}


GEOMETRY_INSTRUCTIONS='''Design ONLY the geometry of one continuous 3D educational cutaway.
Return the JSON schema. No narration and no actions. Match the user's actual device and the supplied narration.
Coordinates are 0..100, y DOWN. Give each part a unique short name, supported shape/color,
pivot [x,y], and points. Whole device must span at least 40 units. Keep useful clearances.
For plate/oval/gear and manufactured or anatomical components, points are two bounding-box corners.
For contour use at least three outline vertices. For pipe/path/wire use ordered route points.
Spring uses its two attached endpoints. Keep housing and supports fixed; make independently moving
pieces separate. Do not overlap distinct solid parts unless they are actually assembled that way.
Electrical: use native battery, resistor, capacitor, switch, coil, motor, bulb, led, terminal.
Do not substitute boxes for complete electrical components. Switch is a composite base AND blade;
it can be opened/closed with a switch action later, so no separate blade is needed.
Wire links MUST list both end terminals as strings: ["Battery:positive","Switch:left"].
Battery has positive at TOP centre, negative at BOTTOM centre. Other components have left/right
terminals at vertical centre. Electrolytic capacitor left is positive, right negative.
Use links:[] on non-wires. The app attaches wire endpoints exactly to those terminals.
Route a complete circuit from battery positive through the requested components to negative.
Place battery at the left, series components around it with non-crossing wire routes and space
for the full switch travel. Do not short out components. Insulation is built into the wire mesh.
Biology: use the supported anatomical shapes, not generic blocks. Represent microscopic objects
as labeled illustrative markers; never move an intact pill into a blood vessel.
No fabricated drug-specific claims, doses, treatment instructions or measured values.
Only necessary functional parts. Do not generate placeholder actions or extra explanatory text.'''

GEOMETRY_INSTRUCTIONS+='''
Example of the JSON form (design the requested device, not this example):
{"parts":[{"name":"Support","shape":"plate","color":"steel","pivot":[50,75],"points":[[10,70],[90,80]],"links":[]},
{"name":"Rotor","shape":"gear","color":"gold","pivot":[50,45],"points":[[30,25],[70,65]],"links":[]}]}
Choose each shape independently: a Battery is battery, a Resistor is resistor, a Switch is switch.
For a circuit you MUST include the wire parts too. A battery is only a small part of the board,
never a bounding box covering the whole scene. Native components take exactly TWO opposite corners.'''

GEOMETRY_INSTRUCTIONS+='''
Example of TWO WIRE PARTS joining a battery and load (adapt to the requested circuit):
{"name":"Feed wire","shape":"wire","color":"red","pivot":[15,30],"points":[[15,30],[15,20],[65,20],[65,50]],"links":["Battery:positive","Load:left"]}
{"name":"Return wire","shape":"wire","color":"blue","pivot":[85,50],"points":[[85,50],[90,80],[15,80],[15,70]],"links":["Load:right","Battery:negative"]}
Wires are SEPARATE parts in the same parts array. Do not attach links to solid components.
Built-in component meshes ALREADY contain their cans, stripes, contacts, leads, bands and insulation;
do not add duplicate decorative parts for those details.'''


ACTION_INSTRUCTIONS='''Animate the VALIDATED PARTS supplied below. Return ONLY actions JSON.
Never redesign the geometry. Refer to the exact supplied part names. Spread the causal sequence
over the numbered narration beats. One continuing motion can span later beats; do not invent
movements merely to fill three beats. Omit zero-movement placeholder actions.
beat is a body beat 1..N, after hook 0. start/end are fractions of that beat, with start < end;
use 0.10 and 0.85 unless a physical event requires another interval.
move [dx,dy] in board units, turn [degrees,0], expand [relative x,relative y].
These geometric changes persist and add to earlier changes. Move attached pieces together.
Motor turn rotates its rotor only. Do not rotate whole batteries, resistors or switch bases.
switch [1,0] closes a native switch blade; [0,0] opens it. Default switch is OPEN.
current [signed level,0] persists on wire: +1 along its listed points, -1 opposite, 0 stops.
Use levels between -1 and 1. Consecutive nonzero levels interpolate smoothly, so fading current
can use 1, 0.6, 0.2, 0.02 in successive beats. Opening a switch immediately stops its branch.
Use current for ongoing electrical flow; flow [direction,0] is TEMPORARY during one beat.
charge [fraction,0] changes a capacitor's stored charge from 0 to 1; this is not heat or motion.
For a charging process raise charge as current decreases. Never send particles through dielectric.
Energize [0..1,0] changes heat/light/magnetic field, not a capacitor's charge. Default all states 0.
Pulse [Hz,amplitude] is a persistent biological pulse. Dissolve [fraction,0] works on a tablet/capsule.
Every action must show its matching narration. Keep valid contact and attachment geometry.
Current actions must target WIRE names, never a resistor, capacitor or battery. A charging
capacitor needs its own charge actions as well as current on the wires. Close the switch
before starting current. Use a later beat for current and charge if the switch closes in beat 1.
Return only the necessary motion and state changes, within the supplied parts' clearances.'''

ACTION_INSTRUCTIONS+='''
Use actual nonzero amounts: a quarter turn is [90,0], upward travel is [0,-12],
and returning by the same distance is [0,12]. These illustrate units, not a device design.
Choose amounts that fit the validated mechanism. [0,0] cannot rotate or translate anything.'''


def plan_custom_mechanism(prompt,scenes,request,key,model,progress=None):
    """Keep validated parts when repairing actions, rather than restarting a giant plan."""
    beats=len(scenes)
    brief='User prompt (preserve all details):\n'+prompt+'\nNarration:\n'+'\n'.join(
        f"{i}. {scene['narration']}" for i,scene in enumerate(scenes) if i)
    shapes,electrical,biology=_domain(brief)
    instructions=GEOMETRY_INSTRUCTIONS
    if not electrical:
        instructions=instructions[:instructions.index('Electrical:')]+instructions[instructions.index('Biology:'):]
        instructions=instructions[:instructions.index('Choose each shape independently:')]
    if not biology:
        instructions=instructions[:instructions.index('Biology:')]+instructions[instructions.index('Only necessary'):]
    parts=None;last_error=None;raw=None;legacy=None
    for attempt in range(2):
        try:
            if attempt and progress:progress('mechanism_retry')
            raw=request(brief,instructions,parts_schema(beats,shapes),key,False,True,model)
            data=planning_json(raw)
            parts=_parts_data(data,beats)
            # Accept complete saved/legacy responses without an extra model call.
            if 'actions' in data:
                legacy=data
                try:
                    if data['actions'] and isinstance(data['actions'][0],dict):
                        return _finish_actions(parts,data['actions'],beats)
                    return parse_mechanism_rows(data,beats)
                except (ValueError,KeyError,TypeError,AttributeError,IndexError) as error:last_error=error
            break
        except (ValueError,KeyError,TypeError,AttributeError,IndexError,requests.RequestException) as error:
            last_error=error
            print(f'[AI geometry] Attempt {attempt+1}: {type(error).__name__}: {error}',flush=True)
            if attempt:raise
            instructions+='\nRepair this geometry issue: '+str(error)+'. Return a complete parts object only.'
            if raw is not None:
                instructions+='\nPrevious geometry to repair:\n'+str(raw)[:12000]
    action_brief=brief+'\nValidated parts (do not change):\n'+json.dumps(_plain_parts(parts),separators=(',',':'))
    action_instructions=ACTION_INSTRUCTIONS
    if not electrical:
        start=action_instructions.index('Motor turn')
        end=action_instructions.index('Pulse [Hz')
        action_instructions=action_instructions[:start]+action_instructions[end:]
        start=action_instructions.index('Current actions must')
        end=action_instructions.index('Return only',start)
        action_instructions=action_instructions[:start]+action_instructions[end:]
    action_brief+='\nSupported effects for each part:\n'+json.dumps({p['name']:allowed_effects(p['shape']) for p in parts})
    if last_error:
        action_instructions+='\nPrevious validation issue: '+str(last_error)
        if legacy is not None:
            action_brief+='\nPrevious draft to correct:\n'+json.dumps(legacy,separators=(',',':'))[:10000]
    for attempt in range(2):
        try:
            if attempt and progress:progress('mechanism_retry')
            raw=request(action_brief,action_instructions,actions_schema(beats,parts),key,False,True,model)
            data=planning_json(raw)
            actions=data['actions']
            if actions and isinstance(actions[0],str):
                # Legacy row fixtures and previously cached plans remain readable.
                source=data.get('parts') or (legacy.get('parts') if legacy else None)
                if source:
                    return parse_mechanism_rows({'parts':source,'actions':actions},beats)
            return _finish_actions(parts,actions,beats)
        except (ValueError,KeyError,TypeError,AttributeError,IndexError,requests.RequestException) as error:
            print(f'[AI actions] Attempt {attempt+1}: {type(error).__name__}: {error}',flush=True)
            if attempt:raise
            if isinstance(error,requests.RequestException):
                action_instructions+='\nThe previous request did not finish. Keep the action list compact.'
            else:
                action_instructions+='\nRepair this action issue: '+str(error)+'. Keep the validated parts unchanged.'
                action_brief+='\nPrevious actions to correct:\n'+str(raw)[:10000]
