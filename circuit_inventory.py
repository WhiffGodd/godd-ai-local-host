# SPDX-License-Identifier: MIT
"""Validate electrical inventories and complete only an unambiguous series gap."""
import copy
from collections import Counter
from types import SimpleNamespace

from mechanism_dynamics import conducting_wires, series_wire_directions


TWO_TERMINAL_SHAPES = frozenset(('resistor','capacitor','coil','motor','bulb','led','terminal','relay','switch'))


class CircuitInventoryError(ValueError):
    def __init__(self, message, components, connections):
        super().__init__(message)
        self.inventory = copy.deepcopy(dict(components=components, connections=connections))


def inventory_ports(part):
    if part['shape']=='battery':return ('positive','negative')
    if part['shape'] in TWO_TERMINAL_SHAPES or part.get('electrical_role') in ('source','load','conductor'):
        return ('left','right')
    return ()


def inventory_graph(components, connections):
    graph=[SimpleNamespace(shape=p['shape'],part=SimpleNamespace(label=p['name']),links=(),electrical_role=p.get('electrical_role','')) for p in components]
    graph.extend(SimpleNamespace(shape='wire',part=SimpleNamespace(label=w['name']),links=[v.rsplit(':',1) for v in w['links']]) for w in connections)
    return graph


def complete_inventory_circuit(components, connections):
    """Preserve declared branches; infer at most one missing wire in a series loop.

    Never redirect a wire, guess a branch, discard an idle lead, or connect two
    terminals of the same part. Ambiguous topology goes back to the model with
    the precise open terminals and disconnected wire names.
    """
    connections=copy.deepcopy(connections)
    sources=[p for p in components if p['shape']=='battery' or p.get('electrical_role')=='source']
    if not sources or not connections:return connections
    closed={p['name'].casefold():True for p in components if p['shape']=='switch'}
    def live(wires):return conducting_wires(inventory_graph(components,wires),closed)
    missing={w['name'] for w in connections}-live(connections)
    if not missing:return connections
    usage=Counter(link for wire in connections for link in wire['links'])
    free=[p['name']+':'+port for p in components for port in inventory_ports(p) if not usage[p['name']+':'+port]]
    if (len(sources)==1 and len(free)==2 and max(usage.values(),default=0)<=1
            and free[0].rsplit(':',1)[0]!=free[1].rsplit(':',1)[0] and len(components)+len(connections)<24):
        names={p['name'].casefold() for p in components}|{w['name'].casefold() for w in connections}
        base='Circuit return' if any(link==sources[0]['name']+':'+inventory_ports(sources[0])[1] for link in free) else 'Circuit connection'
        name=base;index=2
        while name.casefold() in names:name=f'{base} {index}';index+=1
        candidate=dict(name=name,color='blue' if base=='Circuit return' else 'red',links=free)
        completed=[*connections,candidate]
        # A single series path proves there is no invented branch or bypass.
        if (series_wire_directions(inventory_graph(components,completed))
                and not ({w['name'] for w in completed}-live(completed))):
            return completed
    message=('The wire inventory is incomplete. Wires outside a source-to-return path with switches closed: '
             +', '.join(sorted(missing))+'. Unconnected terminals: '+(', '.join(free) or 'none')
             +'. Keep the physical components; repair only the connections. Connect the source through the switch/load and back to its return terminal. '
             'Do not put both ends of a load on the same node or short the source.')
    raise CircuitInventoryError(message,components,connections)


def simple_series_connections(components, previous):
    """Construct the unique basic source/optional-switch/single-load circuit.

    This is a role-based compiler, not a device template. Multiple loads,
    sources, switches or additional conductors require an explicit topology.
    Existing valid circuits never reach this fallback.
    """
    sources=[];switches=[];loads=[]
    for part in components:
        if not inventory_ports(part):continue
        if part['shape']=='battery' or part.get('electrical_role')=='source':sources.append(part)
        elif part['shape']=='switch':switches.append(part)
        elif part['shape'] in TWO_TERMINAL_SHAPES-{'switch','terminal'} or part.get('electrical_role')=='load':loads.append(part)
        else:return None
    if len(sources)!=1 or len(loads)!=1 or len(switches)>1:return None
    source=sources[0];load=loads[0];positive,negative=inventory_ports(source)
    start=source['name']+':'+positive;end=source['name']+':'+negative
    pairs=[]
    if switches:
        switch=switches[0]['name'];pairs.append((start,switch+':left'));start=switch+':right'
    pairs.extend(((start,load['name']+':left'),(load['name']+':right',end)))
    if len(components)+len(pairs)>24:return None
    wires=[]
    for index,(a,b) in enumerate(pairs):
        # Keep a correctly declared wire's name/color/orientation where possible.
        match=next((wire for wire in previous if isinstance(wire,dict) and isinstance(wire.get('links'),list)
                    and len(wire['links'])==2 and set(wire['links'])=={a,b}),None)
        wires.append(copy.deepcopy(match) if match else dict(name=('Return lead' if b==end else 'Supply lead' if index==0 else 'Switched lead'),
                                                              color='blue' if b==end else 'red',links=[a,b]))
    return wires
