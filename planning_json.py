# SPDX-License-Identifier: MIT
"""Read complete planner objects, including providers that wrap JSON in prose."""
import json


def planning_json(value):
    if isinstance(value,dict):
        return value
    if not isinstance(value,str):
        raise ValueError('The planner response must be a complete JSON object')
    value=value.lstrip('\ufeff').strip()
    try:
        result=json.loads(value)
    except json.JSONDecodeError:
        decoder=json.JSONDecoder()
        result=None
        for index,char in enumerate(value):
            if char!='{':
                continue
            try:
                candidate,end=decoder.raw_decode(value,index)
            except json.JSONDecodeError:
                continue
            if not isinstance(candidate,dict):
                continue
            # Do not salvage a nested fragment from an unfinished outer plan.
            prefix=value[:index]
            if '{' in prefix or '[' in prefix:
                continue
            if value[end:].strip().strip('`').strip() and '{' in value[end:]:
                raise ValueError('The planner returned multiple JSON objects')
            result=candidate
            break
        if result is None:
            raise ValueError('The planner returned incomplete or invalid JSON') from None
    if not isinstance(result,dict):
        raise ValueError('The planner response must be a JSON object')
    return result


def compact_local_schema(schema):
    """Share repeated solid definitions so local inference keeps a small context."""
    import copy
    result=copy.deepcopy(schema)
    variants=result.get('properties',{}).get('parts',{}).get('items',{}).get('anyOf',[])
    geometries=[v['properties']['geometry'] for v in variants if 'geometry' in v.get('properties',{})]
    if len(geometries)>1 and all(g==geometries[0] for g in geometries):
        result.setdefault('$defs',{})['solidGeometry']=geometries[0]
        for variant in variants:
            if 'geometry' in variant.get('properties',{}):variant['properties']['geometry']={'$ref':'#/$defs/solidGeometry'}
    return result
