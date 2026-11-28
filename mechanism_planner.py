# SPDX-License-Identifier: MIT
"""Bounded, staged planning shared by every custom 3D mechanism."""
import copy
import json
import math
import re

import requests

from biological_components import BIOLOGICAL_SHAPES
from mechanism_animation import ELECTRICAL_SHAPES, PALETTE, SHAPES, _electrical_shape, mechanism_schema, parse_mechanism_rows, read_mechanism
from planning_json import planning_json
from mechanism_dynamics import conducting_wires, series_wire_directions
from solid_geometry import fit_solids, solid_schema
from connection_routing import route_wire
from mechanism_attachments import validate_bindings
from circuit_inventory import CircuitInventoryError, complete_inventory_circuit, inventory_ports, simple_series_connections


def _key(name):
    return ' '.join(name.replace('_',' ').split()).casefold()


def terminal_port(value,shape):
    port=value.strip().casefold().replace('_',' ')
    port=re.sub(r'\b(?:terminal|contact|lead|port)\b','',port).strip()
    if port not in ('+','-'):port=port.strip(' -:')
    port={'+':'positive','-':'negative','pos':'positive','neg':'negative'}.get(port,port)
    if shape=='battery':return {'top':'positive','bottom':'negative'}.get(port,port)
    return {'positive':'left','negative':'right'}.get(port,port)


def terminal_reference_schema():
    return dict(type='string',pattern=r'^[^:\n]+:(positive|negative|left|right)$',maxLength=60)


def electrical_ports(part):
    x,y=zip(*part['points'])
    l,t,r,b=min(x),min(y),max(x),max(y)
    if part['shape']=='battery':
        return {'positive':[(l+r)/2,t],'negative':[(l+r)/2,b]}
    if part['shape'] in ELECTRICAL_SHAPES and part['shape']!='wire' or part['shape']=='solid' and part.get('electrical_role'):
        return {'left':[l,(t+b)/2],'right':[r,(t+b)/2]}
    return {}


def _layout_coordinates(data):
    """Fit a complete finite model into board space with one shared transform.

    No point is independently clamped: shape proportions, joint positions and
    pivots retain their relationship. Action planning receives the fitted parts.
    Malformed pairs and nonfinite values must be repaired by the model.
    """
    data=copy.deepcopy(data)
    coordinates=[]
    def pair(value,field):
        if not isinstance(value,list) or len(value)!=2:
            raise ValueError(f'{field} needs exactly [x,y], not {value!r}; omit z coordinates')
        result=[]
        for number in value:
            if isinstance(number,str) and re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?',number.strip()):
                number=float(number)
            if type(number) not in (float,int) or abs(number)>1e6 or not math.isfinite(number):
                raise ValueError(f'{field} needs finite numeric x/y values within a reasonable board scale; received {value!r}')
            result.append(number)
        coordinates.append(result)
        return result
    for item in data['parts']:
        if not isinstance(item,dict):continue  # Existing saved row format.
        name=item.get('name','Unnamed part')
        item['pivot']=pair(item.get('pivot'),f'{name}.pivot')
        if not isinstance(item.get('points'),list):
            raise ValueError(f'{name}.points needs an array of [x,y] pairs')
        item['points']=[pair(p,f'{name}.points[{i}]') for i,p in enumerate(item['points'])]
    if not coordinates:return data
    left,top=map(min,zip(*coordinates));right,bottom=map(max,zip(*coordinates))
    span=max(right-left,bottom-top)
    if span and (min(left,top)<0 or max(right,bottom)>100 or span<34):
        scale=84/span
        cx,cy=(left+right)/2,(top+bottom)/2
        for point in coordinates:
            point[0]=50+(point[0]-cx)*scale
            point[1]=50+(point[1]-cy)*scale
    return data


def _connection_parts(data):
    """Compile explicit connections to wires; physical components have no links."""
    data=copy.deepcopy(data)
    connections=data.get('connections',[])
    if not isinstance(connections,list) or len(connections)>24:
        raise ValueError('connections must be an array of at most 24 routed wires')
    for i,wire in enumerate(connections):
        if not isinstance(wire,dict):raise ValueError(f'connections[{i}] must describe a wire')
        points=wire.get('points')
        if not isinstance(points,list) or len(points)<2:
            raise ValueError(f'connections[{i}].points needs at least two route points')
        data['parts'].append(dict(name=wire.get('name',f'Wire {i+1}'),shape='wire',
            color=wire.get('color','red'),pivot=points[0],points=points,links=wire.get('links',[])))
    return data


def _parts_data(data,beats):
    """Canonicalize geometry without inventing any animation actions."""
    data=_layout_coordinates(_connection_parts(data))
    flat=[]
    for item in data['parts']:
        if not isinstance(item,dict):continue
        points=item.get('points',[])
        shape=item.get('shape')
        if shape=='solid' and 'geometry' in item:
            item['geometry']=fit_solids(item['geometry'])
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
        filled=shape in ('solid','plate','oval','gear') or shape in ELECTRICAL_SHAPES and shape!='wire' or shape in BIOLOGICAL_SHAPES and shape not in ('blood_vessel','ureter','digestive_tube')
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
        if p.geometry:entries[-1]['geometry']=[piece.data() for piece in p.geometry]
        if p.electrical_role:entries[-1]['electrical_role']=p.electrical_role
        if p.parent:entries[-1]['parent']=p.parent
        if p.rotation_axis!='z':entries[-1]['rotation_axis']=p.rotation_axis
    by_name={_key(p['name']):p for p in entries}
    for part in entries:
        links=part['links']
        if not links:
            if (part['shape']=='wire' and source and 'links' in source[_key(part['name'])]
                    and any(p['shape']=='battery' for p in entries)):
                raise ValueError(f"{part['name']}: electrical wires need two terminal links")
            continue
        if part['shape']!='wire':
            raise ValueError(f"{part['name']} is a physical {part['shape']}, not a wire: remove its links field and put external wires in the top-level connections array, referencing {part['name']}:left/right")
        if not isinstance(links,list) or len(links)!=2:
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
            port=terminal_port(port,target['shape'])
            if port not in ports:
                raise ValueError(f"{part['name']}: {target['name']} has terminals {', '.join(ports)}, not {port}")
            endpoints.append(ports[port]);canonical.append([target['name'],port])
        part['points'][0],part['points'][-1]=endpoints
        part['pivot']=endpoints[0]
        part['links']=canonical
    validated,_=read_mechanism({'parts':entries,'actions':[]},beats,require_animation=False)
    if any(p.shape=='battery' or p.electrical_role=='source' for p in validated) and any(p.shape=='wire' and p.links for p in validated):
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
    part['additionalProperties']=False
    part['properties']['shape']['enum']=[s for s in shapes if s not in ('wire','solid')]
    variants=[part]
    if 'solid' in shapes:
        solid=copy.deepcopy(part)
        solid['properties']['shape']={'type':'string','const':'solid'}
        solid['properties']['geometry']=solid_schema(PALETTE)
        solid['required'].append('geometry')
        solid['properties']['points']['maxItems']=2
        variants.append(solid)
    properties={'parts':{'type':'array','minItems':1,'maxItems':24,'items':{'anyOf':variants}}}
    required=['parts']
    if 'wire' in shapes:
        properties['connections']=dict(type='array',maxItems=24,items=dict(type='object',additionalProperties=False,
            properties=dict(name=dict(type='string'),color=dict(type='string',enum=list(PALETTE)),
                points=copy.deepcopy(part['properties']['points']),
                links=dict(type='array',minItems=2,maxItems=2,items=terminal_reference_schema())),
            required=['name','color','points','links']))
        required.append('connections')
    return {'type':'object','additionalProperties':False,'properties':properties,'required':required}


def allowed_effects(shape):
    effects=['move','turn','spin','expand','energize']
    if shape=='switch':effects.remove('turn');effects.remove('spin');effects.append('switch')
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


def inventory_schema(shapes,electrical):
    component=dict(type='object',additionalProperties=False,properties=dict(
        name=dict(type='string',maxLength=42,pattern=r'^[^:\n]+$'),parent=dict(type='string',maxLength=42),rotation_axis=dict(type='string',enum=['x','y','z']),shape=dict(type='string',enum=[s for s in shapes if s!='wire']),
        function=dict(type='string'),motion=dict(type='string',enum=['fixed','rotate','slide','deform','flow','state'])),
        required=['name','shape','function','motion'])
    properties=dict(components=dict(type='array',minItems=1,maxItems=16,items=component))
    if electrical:
        component['properties']['electrical_role']=dict(type='string',enum=['none','source','load','conductor'])
        component['required'].append('electrical_role')
        properties['connections']=dict(type='array',maxItems=16,items=dict(type='object',additionalProperties=False,
            properties=dict(name=dict(type='string'),color=dict(type='string',enum=list(PALETTE)),
                links=dict(type='array',minItems=2,maxItems=2,items=terminal_reference_schema())),required=['name','color','links']))
    return dict(type='object',additionalProperties=False,properties=properties,required=list(properties))


INVENTORY_INSTRUCTIONS='''Identify the actual physical parts and their functions for this prompt.
Return a compact functional inventory, not coordinates, geometry, narration or actions.
Use the smallest assembly that covers the prompt, at most 16 components. Use each component's
actual name. Choose native manufactured/anatomical shapes when available; for unfamiliar
parts choose solid, which supports compound 3D construction. Distinguish a rotating rotor
from a fixed housing or stator. Motion says fixed, rotate, slide, deform, flow or state.
Native capacitor means a complete physical capacitor: never use it for a housing just
because the housing is cylindrical. Native motor means a complete motor, not an isolated
magnet/stator. Shafts, casings, magnets and separate rotors use solid geometry.
Native asset capabilities: motor ALREADY contains an open-front metal casing, stationary
N/S magnets, rotating copper coils, commutator, brushes and output shaft. Spin on motor
animates its internal rotor/shaft while its case and magnets remain stationary. Use this
complete native component when it covers the described machine; do not rebuild its included
parts as crude cylinders or boxes. Coil already has copper windings, core and visible field;
capacitor already has a marked can, leads and foil cutaway. Battery has a marked cell and
internal layers. Use native assets for their actual identity and compound solids for parts
they do not cover. A single complete native component can be sufficient for a mechanism.
Use parent for rigid attachments, naming the exact parent component; omit it for roots.
Use rotation_axis x/y/z for the actual shaft direction; z points toward the camera.
Native motor's built-in shaft points along z. Other axes are available for custom parts.
Drive motion on the root only. Rigid children follow it, keeping their relative positions;
independently sliding or rotating joints are not rigid attachments. No cyclic parents.
Do not reduce the whole requested mechanism to a box. Match the user's described system.
If electrical, put EXTERNAL WIRES in connections only, with name/color/links. Components
have NO links. Each wire links two component-name:terminal strings. Use the EXACT listed
component names, never placeholder aliases like Source or Load unless actually listed.
Every referenced component MUST be listed in components. Battery terminals are positive
and negative. Native resistor, capacitor, coil, motor, switch, bulb, led, terminal and relay
have left/right terminals. Non-electrical solids do not have electrical terminals.
For custom electrical components use solid and declare electrical_role source, load or
conductor; these have left/right terminals too. Being made of metal does not put a part
in the electrical circuit: an iron core, sliding rod or return spring is mechanical unless
the prompt explicitly says it carries current between contacts. A physical external power supply is a
source. Use none for purely mechanical parts. Sources must have a complete return path.
A series source-switch-load circuit needs THREE wires, including load-to-source return.
Only the switch and electrical load belong in that path; mechanical rods/springs do not.
If showing current, include the physical supply and complete return path. Never short
the source. Coil is a component, not a wire. No links across a capacitor's dielectric.
Components plus connections must total at most 24. Use connections:[] if no wiring is needed.
No made-up medical claims or invented measurements. Return only the schema.'''


def _mechanical_electrical_subpart(part):
    """Metal cores/supports are not circuit conductors just because they are metal."""
    if part['shape']!='solid':return False
    text=part['name']+' '+part.get('function','')
    current_purpose=re.search(r'\b(?:current|voltage|circuit|wire|winding|electrode|contact|brush|commutator|conduct(?:s|ing|or|ive)?)s?\b',text,re.I)
    return not current_purpose and bool(re.search(r'\b(?:spring|core|rod|shaft|housing|casing|support|guide|magnet)s?\b',text,re.I))


def _inventory(data,shapes):
    components=data['components']
    if not isinstance(components,list) or not 1<=len(components)<=16:raise ValueError('Inventory needs 1..16 physical components')
    names={};result=[]
    for item in components:
        name=' '.join(item['name'].replace('_',' ').split())
        shape=_electrical_shape(name,item['shape'])
        # Native meshes represent whole components, not every similarly shaped
        # subpart. Preserve a shaft/housing/magnet as its own prompt-built solid.
        if (shape in ELECTRICAL_SHAPES and shape not in ('wire','terminal')
                and re.search(r'\b(?:housing|casing|shaft|rotor|stator|magnet|armature|brush|contact|electrode|plate)s?\b',name,re.I)
                and not (shape=='coil' and re.search(r'\b(?:coil|winding)s?\b',name,re.I))):
            shape='solid'
        if not name or len(name)>42 or _key(name) in names or shape not in shapes or shape=='wire':
            raise ValueError('Use unique short component names and physical component shapes; external wires belong in connections')
        if item.get('motion') not in ('fixed','rotate','slide','deform','flow','state'):
            raise ValueError(f'{name}: choose a supported physical motion')
        role=item.get('electrical_role','none')
        if role not in ('none','source','load','conductor'):raise ValueError(f'{name}: unsupported electrical role')
        if shape!='solid':role='none'  # Native components already define their circuit behavior.
        if shape=='solid' and re.search(r'\b(?:power|voltage|dc)\s+(?:source|supply)\b',name,re.I):role='source'
        clean=dict(name=name,shape=shape,function=item.get('function',''),motion=item['motion'],electrical_role='' if role=='none' else role,parent=item.get('parent',''),rotation_axis='z' if shape=='motor' else item.get('rotation_axis','z'))
        if role=='conductor' and _mechanical_electrical_subpart(clean):clean['electrical_role']=''
        names[_key(name)]=clean;result.append(clean)
    parents={}
    for part in result:
        if part['rotation_axis'] not in ('x','y','z'):raise ValueError(f'{part["name"]}: choose rotation_axis x, y or z')
        if part['parent']:
            parent=names.get(_key(part['parent']))
            if parent is None:raise ValueError(f'{part["name"]}: rigid parent {part["parent"]!r} is missing')
            parents[part['name']]=parent['name'];part['parent']=parent['name']
    validate_bindings(parents,{p['name'] for p in result})
    return _inventory_connections(result,data.get('connections',[]))


def _inventory_connections(components,wires):
    try:return _canonical_inventory_connections(components,wires)
    except CircuitInventoryError:
        replacement=simple_series_connections(components,wires)
        if replacement is None:raise
        return _canonical_inventory_connections(components,replacement)


def _canonical_inventory_connections(components,wires):
    result=copy.deepcopy(components)
    names={_key(p['name']):p for p in result}
    if not isinstance(wires,list) or len(wires)+len(result)>24:raise ValueError('Components and wire connections together must fit 24 parts')
    missing=set()
    for wire in wires:
        for link in wire.get('links',[]):
            if isinstance(link,str) and ':' in link:
                target=link.rsplit(':',1)[0]
                if _key(target) not in names:missing.add(target)
    if missing:
        raise ValueError(f'{sorted(missing)} missing from components. Use the actual component names {list(p["name"] for p in result)}, or explicitly add the missing physical supply/load. Fix ALL missing references, not just the first wire')
    connections=[];seen=set(names)
    for index,wire in enumerate(wires):
        name=wire.get('name','')[:42]
        if not name or _key(name) in seen:
            # Wires are referenced only by their component terminals at this stage;
            # repairing a display-name collision cannot change circuit topology.
            base=name[:28] or 'Connection';suffix=index+1
            name=f'{base} wire {suffix}'
            while _key(name) in seen:
                suffix+=1;name=f'{base} wire {suffix}'
        seen.add(_key(name));links=wire['links'];canonical=[]
        if not isinstance(links,list) or len(links)!=2:raise ValueError(f'{name}: a wire connects exactly two named terminals')
        for link in links:
            if not isinstance(link,str) or ':' not in link:raise ValueError(f'{name}: terminal references must be Component:port')
            target,port=link.rsplit(':',1);part=names.get(_key(target))
            if part is None:raise ValueError(f'{name}: {target!r} is missing from components; list it before wiring it')
            if part['shape']=='solid' and not part['electrical_role']:
                if _mechanical_electrical_subpart(part):
                    raise CircuitInventoryError(f"{part['name']} is a mechanical part, not an electrical load. Keep it out of the wired path; connect the source, switches and actual electrical loads with a complete return.",components,wires)
                part['electrical_role']='load'  # An explicitly wired custom two-terminal part.
            ports=electrical_ports(dict(shape=part['shape'],points=[[0,0],[10,10]],electrical_role=part['electrical_role']))
            port=terminal_port(port,part['shape'])
            if port not in ports:raise ValueError(f'{name}: {part["name"]} ({part["shape"]}) has terminals {list(ports)}, not {port}')
            canonical.append(part['name']+':'+port)
        if canonical[0]==canonical[1]:raise ValueError(f'{name}: a wire cannot connect a terminal to itself')
        if wire['color'] not in PALETTE:raise ValueError(f'{name}: use a supported insulation color')
        connections.append(dict(name=name,color=wire['color'],links=canonical))
    try:
        return dict(components=result,connections=complete_inventory_circuit(result,connections))
    except CircuitInventoryError as error:
        # Roles inferred from an invalid wire draft must not turn mechanical
        # parts into electrical loads in the focused repair request.
        error.inventory['components']=copy.deepcopy(components)
        raise


WIRE_REPAIR_INSTRUCTIONS='''Repair ONLY the electrical connections for the supplied fixed inventory.
Return connections JSON, never new components, geometry, narration or actions.
Use the exact component:terminal strings allowed by the schema. Keep the user's
intended circuit and every physical component. Close a source-to-return path
through the intended switches and loads. A switch and load in series need three
wires: source-positive to switch-left, switch-right to load-left, load-right to
source-negative, using the real inventory names. Mechanical rods, return springs
and housings do not need electrical wires. Never short the source or connect both
terminals of a load to the same source terminal. Repair all listed topology issues.'''


def _wiring_schema(inventory):
    wire=copy.deepcopy(inventory_schema(SHAPES,True)['properties']['connections'])
    wire['maxItems']=min(16,24-len(inventory['components']))
    terminals=[p['name']+':'+port for p in inventory['components'] for port in inventory_ports(p)]
    wire['items']['properties']['links']['items']=dict(type='string',enum=terminals)
    return dict(type='object',additionalProperties=False,properties=dict(connections=wire),required=['connections'])


def _geometry_schema(beats,shapes,inventory):
    schema=parts_schema(beats,shapes)
    if inventory is None:return schema
    schema['properties'].pop('connections',None);schema['required']=['parts']
    options=schema['properties']['parts']['items']['anyOf'];variants=[]
    for part in inventory['components']:
        option=next((v for v in options if v['properties']['shape'].get('const')==part['shape']),options[0])
        option=copy.deepcopy(option)
        option['properties']['name']={'type':'string','const':part['name']}
        option['properties']['shape']={'type':'string','const':part['shape']}
        variants.append(option)
    schema['properties']['parts']['minItems']=len(variants)
    schema['properties']['parts']['maxItems']=len(variants)
    schema['properties']['parts']['items']={'anyOf':variants}
    return schema


def _inventory_geometry(data,beats,inventory):
    if inventory is None:return _parts_data(data,beats)
    data=copy.deepcopy(data)
    roles={_key(p['name']):p['electrical_role'] for p in inventory['components']}
    parents={_key(p['name']):p.get('parent','') for p in inventory['components']}
    axes={_key(p['name']):p.get('rotation_axis','z') for p in inventory['components']}
    for part in data['parts']:
        if isinstance(part,dict):part['rotation_axis']=axes.get(_key(part['name']),'z')
        if isinstance(part,dict) and parents.get(_key(part['name'])):part['parent']=parents[_key(part['name'])]
        if isinstance(part,dict) and roles.get(_key(part['name'])):
            part['electrical_role']=roles[_key(part['name'])]
    parts=_parts_data(dict(parts=data['parts']),beats)
    expected={_key(p['name']):p['shape'] for p in inventory['components']}
    actual={_key(p['name']):p['shape'] for p in parts}
    if expected!=actual:raise ValueError(f'Keep exactly the inventoried components and shapes: {expected}; received {actual}')
    by_name={_key(p['name']):p for p in parts};connections=[]
    connected={_key(link.rsplit(':',1)[0]) for w in inventory['connections'] for link in w['links']}
    wired=[p for p in parts if _key(p['name']) in connected and electrical_ports(p)]
    def envelope(part):
        x,y=zip(*part['points']);return min(x),min(y),max(x),max(y)
    def contains(parent,child):
        l,t,r,b=envelope(parent);cl,ct,cr,cb=envelope(child)
        return l<=cl and t<=ct and r>=cr and b>=cb and (r-l>cr-cl+1e-6 or b-t>cb-ct+1e-6)
    # In a cutaway, a parent envelope can contain exposed, separately wired
    # internals. Its bounding rectangle is not a filled obstacle on that plane.
    obstacles=[p['points'] for p in wired if not any(p is not child and contains(p,child) for child in wired)]
    for wire in inventory['connections']:
        (an,ap),(bn,bp)=[link.rsplit(':',1) for link in wire['links']]
        a,b=by_name[_key(an)],by_name[_key(bn)]
        start,end=electrical_ports(a)[ap],electrical_ports(b)[bp]
        # Unconnected internal components may enclose another component in a
        # cutaway. Route around the wired bodies, not their entire parent assembly.
        points=route_wire(start,end,ap,bp,obstacles)
        connections.append({**wire,'points':points})
    return _parts_data(dict(parts=parts,connections=connections),beats)


GEOMETRY_INSTRUCTIONS='''Design ONLY the geometry of one continuous 3D educational cutaway.
Return the JSON schema. No narration and no actions. Match the user's actual device and the supplied narration.
Coordinates are 0..100, y DOWN. Give each part a unique short name, supported shape/color,
pivot [x,y], and points. Whole device must span at least 40 units. Keep useful clearances.
For solid/plate/oval/gear and manufactured or anatomical components, points are two bounding-box corners.
For contour use at least three outline vertices. For pipe/path/wire use ordered route points.
Spring uses its two attached endpoints. Keep housing and supports fixed; make independently moving
pieces separate. Do not overlap distinct solid parts unless they are actually assembled that way.
For unfamiliar parts use shape solid with geometry: a compound of 1..6 box, cylinder, sphere,
ring or shell primitives. A shell is an open cutaway casing; use it for housings so inner
moving parts stay visible. Model the distinctive silhouette, openings, shafts and surface pieces;
do not use a single colored box for an unfamiliar machine. Each independently moving part
gets its own name and pivot. Local center and size are normalized triples in the part's box,
0..1, and center +/- size/2 must fit inside it. Axis x/y/z is the cylinder/ring's shaft axis.
Use metallic colors for manufactured surfaces. Prefer the smallest recognizable assembly.
For distinctive manufactured parts use lathe or extrude with a closed profile of 3..32
normalized [x,y] points. Extrude uses x-right/y-down outline coordinates. Lathe uses
[radius,height] with radius 0..1 and height 0..1, revolved about the specified axis.
Profiles must have area and cannot cross themselves. These operations can make stepped
shafts, hollow tubes, contoured levers, knobs and casings instead of stacking plain blocks.
Example compound part: {"name":"Flanged spindle","shape":"solid","color":"steel",
"pivot":[50,50],"points":[[25,25],[75,75]],"geometry":[
{"primitive":"cylinder","center":[0.5,0.5,0.5],"size":[0.2,0.2,1],"axis":"z","color":"steel"},
{"primitive":"ring","center":[0.5,0.5,0.25],"size":[0.8,0.8,0.15],"axis":"z","color":"gold"}]}
Only necessary functional parts. No placeholder actions or extra explanatory text.'''

ELECTRICAL_LAYOUT_INSTRUCTIONS='''Electrical: use native battery, resistor, capacitor, switch, coil, motor, bulb, led, terminal.
Do not substitute boxes for complete electrical components. Switch is a composite base AND blade;
it can be opened/closed with a switch action later, so no separate blade is needed.
The parts array contains PHYSICAL COMPONENTS only. Never put links on them, even links:[].
Wires belong ONLY in the separate top-level connections array. Each connection has a name,
color, points route and links naming its two end terminals: ["Battery:positive","Switch:left"].
Battery has positive at TOP centre, negative at BOTTOM centre. Other components have left/right
terminals at vertical centre. Electrolytic capacitor left is positive, right negative.
The app attaches wire endpoints exactly to those terminals. Coil is a physical component
with left/right terminals; Coil is NOT a wire. Model subparts of a cutaway as separate solids.
Route a complete circuit from battery positive through the requested components to negative.
Place battery at the left, series components around it with non-crossing wire routes and space
for the full switch travel. Do not short out components. Insulation is built into the wire mesh.
Example connection: {"name":"Feed","color":"red","points":[[15,30],[15,20],[65,20],[65,50]],
"links":["Battery:positive","Load:left"]}. Output connections:[] if no electrical wiring is needed.
Native meshes already include cans, stripes, leads, winding, bands and insulation. Do not
duplicate those details as extra parts. A full motor is a cutaway with its own visible rotor;
if you model individual rotor/stator pieces instead, give them separate solid geometry.'''

BIOLOGY_LAYOUT_INSTRUCTIONS='''Biology: use the supported anatomical shapes, not generic blocks. Represent microscopic objects
as labeled illustrative markers; never move an intact pill into a blood vessel.
No fabricated drug-specific claims, doses, treatment instructions or measured values.'''


ACTION_INSTRUCTIONS='''Animate the VALIDATED PARTS supplied below. Return ONLY actions JSON.
Never redesign the geometry. Refer to the exact supplied part names. Spread the causal sequence
over the numbered narration beats. One continuing motion can span later beats; do not invent
movements merely to fill three beats. Omit zero-movement placeholder actions.
beat is a body beat 1..N, after hook 0. start/end are fractions of that beat, with start < end;
use 0.10 and 0.85 unless a physical event requires another interval.
move [dx,dy] in board units, turn [degrees,0], expand [relative x,relative y].
Spin [revolutions per second,0] is continuing rotation: use 0.3..1 for a readable mechanism.
Use spin for continuously rotating parts, not tiny turn angles. Spin persists across
later narration beats. All parts rigidly attached to one rotating assembly must start
at the same time and speed, including its windings, core, commutator and output shaft.
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
    inventory=None;prefetched=None;wiring_repair=None
    if progress:progress('mechanism_inventory')
    for attempt in range(2):
        try:
            if wiring_repair is None:
                raw=request(brief,INVENTORY_INSTRUCTIONS,inventory_schema(shapes,electrical),key,False,True,model)
            else:
                repair_brief=brief+'\nFIXED COMPONENTS AND PREVIOUS CONNECTIONS:\n'+json.dumps(wiring_repair,separators=(',',':'))
                raw=request(repair_brief,WIRE_REPAIR_INSTRUCTIONS,_wiring_schema(wiring_repair),key,False,True,model)
            data=planning_json(raw)
            if wiring_repair is not None:
                inventory=_inventory_connections(wiring_repair['components'],data['connections'])
            elif 'parts' in data:
                # Saved responses from the former two-stage planner remain readable.
                prefetched=data
            else:inventory=_inventory(data,shapes)
            break
        except (ValueError,KeyError,TypeError,AttributeError,IndexError,requests.RequestException) as error:
            print(f'[AI inventory] Attempt {attempt+1}: {type(error).__name__}: {error}',flush=True)
            if attempt:raise
            if isinstance(error,CircuitInventoryError):wiring_repair=error.inventory
            if progress:progress('mechanism_retry')
            brief+='\nRepair the component inventory: '+str(error)
            if 'raw' in locals():brief+='\nPrevious inventory:\n'+str(raw)[:10000]
    instructions=GEOMETRY_INSTRUCTIONS
    if electrical:instructions+='\n'+ELECTRICAL_LAYOUT_INSTRUCTIONS
    if biology:instructions+='\n'+BIOLOGY_LAYOUT_INSTRUCTIONS
    geometry_brief=brief
    if inventory is not None:
        geometry_brief+='\nFIXED INVENTORY (model these exact parts):\n'+json.dumps(inventory,separators=(',',':'))
        instructions+='\nThe inventory is already validated. Return ONLY parts for the exact named components. Do not output connections: the app routes those fixed connections. Never rename a component or change its shape.'
    if progress:progress('mechanism_parts')
    parts=None;last_error=None;raw=None;legacy=None
    for attempt in range(2):
        try:
            if attempt and progress:progress('mechanism_retry')
            if prefetched is not None:
                data=prefetched;prefetched=None;raw=json.dumps(data)
            else:
                raw=request(geometry_brief,instructions,_geometry_schema(beats,shapes,inventory),key,False,True,model)
                data=planning_json(raw)
            parts=_inventory_geometry(data,beats,inventory)
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
    if inventory is not None:action_brief+='\nFunctions and intended motions:\n'+json.dumps(inventory['components'])
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
    if progress:progress('mechanism_actions')
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
            result=_finish_actions(parts,actions,beats)
            if (inventory and re.search(r'\b(?:continu(?:ous|ously)|keeps?\s+(?:spinning|rotating))\b',prompt,re.I)
                    and any(p['motion']=='rotate' for p in inventory['components'])
                    and not any(a.effect=='spin' and a.amount[0] for a in result[1])):
                raise ValueError('The prompt requires continuous rotation. Use persistent spin [0.5,0] on the rotating assembly parts; small finite turn angles do not show continuing operation')
            return result
        except (ValueError,KeyError,TypeError,AttributeError,IndexError,requests.RequestException) as error:
            print(f'[AI actions] Attempt {attempt+1}: {type(error).__name__}: {error}',flush=True)
            if attempt:raise
            if isinstance(error,requests.RequestException):
                action_instructions+='\nThe previous request did not finish. Keep the action list compact.'
            else:
                action_instructions+='\nRepair this action issue: '+str(error)+'. Keep the validated parts unchanged.'
                action_brief+='\nPrevious actions to correct:\n'+str(raw)[:10000]
