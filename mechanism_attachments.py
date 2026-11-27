# SPDX-License-Identifier: MIT
"""Rigid part attachments shared by both rendering backends."""
import numpy as np


def validate_bindings(bindings,groups):
    if not isinstance(bindings,dict):raise ValueError('Rigid attachments must be a dictionary')
    for child,parent in bindings.items():
        if child not in groups or parent not in groups:raise ValueError('A rigid attachment references a missing part')
        seen={child};node=parent
        while node:
            if node in seen:raise ValueError('Rigid attachments contain a cycle')
            seen.add(node);node=bindings.get(node)
    return dict(bindings)


def attachments_for(parts):
    names={p.part.label.casefold():p.part.label for p in parts};bindings={}
    for part in parts:
        if not part.parent:continue
        parent=names.get(part.parent.replace('_',' ').strip().casefold())
        if parent is None:raise ValueError(f'{part.part.label}: attached parent {part.parent!r} does not exist')
        bindings[part.part.label]=parent
    return validate_bindings(bindings,set(names.values()))


def attach_objects(objects,bindings):
    if not bindings:return objects
    bases={}
    for _,_,matrix,group in objects:bases.setdefault(group,np.asarray(matrix))
    resolved={}
    def root(group):
        if group in resolved:return resolved[group]
        parent=bindings.get(group)
        resolved[group]=root(parent) if parent in bases else bases[group]
        return resolved[group]
    inverse={group:np.linalg.inv(matrix) for group,matrix in bases.items() if group in bindings}
    return [(name,material,root(group)@inverse[group]@matrix if group in inverse else matrix,group)
            for name,material,matrix,group in objects]
