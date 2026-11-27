# SPDX-License-Identifier: MIT
"""Headless Blender worker. Accepts validated scene data, never generated Python."""
import argparse
import json
import math
from pathlib import Path
import sys
import traceback

import bpy
from mathutils import Matrix, Vector
import numpy as np

PREFIX='GODD_BLENDER '


def reply(**value):
    print(PREFIX+json.dumps(value,separators=(',',':')),flush=True)


def point_camera(obj,eye,focus):
    forward=(Vector(focus)-Vector(eye)).normalized()
    right=forward.cross(Vector((0,1,0))).normalized()
    up=right.cross(forward).normalized()
    obj.matrix_world=Matrix(((right.x,up.x,-forward.x,eye[0]),
                            (right.y,up.y,-forward.y,eye[1]),
                            (right.z,up.z,-forward.z,eye[2]),(0,0,0,1)))


def hollow_shell():
    vertices=[];faces=[];segments=72
    for i in range(segments+1):
        angle=math.radians(35+290*i/segments)
        for radius,z in ((.5,-.5),(.5,.5),(.41,-.5),(.41,.5)):
            vertices.append((radius*math.cos(angle),radius*math.sin(angle),z))
    for i in range(segments):
        a=i*4;b=(i+1)*4
        faces.extend(((a,b,b+1,a+1),(a+2,a+3,b+3,b+2),
                      (a,a+2,b+2,b),(a+1,b+1,b+3,a+3)))
    faces.extend(((0,1,3,2),(segments*4,segments*4+2,segments*4+3,segments*4+1)))
    mesh=bpy.data.meshes.new('Cutaway shell');mesh.from_pydata(vertices,[],faces);mesh.update()
    obj=bpy.data.objects.new('Cutaway shell',mesh);bpy.context.collection.objects.link(obj)
    return obj


def box_piece(location,dimensions):
    bpy.ops.mesh.primitive_cube_add(size=1,location=location)
    obj=bpy.context.object;obj.dimensions=dimensions
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    return obj



def profile_object(desc):
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    from parametric_profiles import read_profile,profile_mesh
    profile=read_profile(desc.get('profile'),'Blender part')
    mesh=bpy.data.meshes.new('Manufactured profile')
    if desc['primitive']=='lathe':
        vertices=profile_mesh('lathe',profile,96)
        mesh.from_pydata(vertices[:,:3].tolist(),[],np.arange(len(vertices)).reshape(-1,3).tolist());mesh.update()
        for polygon in mesh.polygons:polygon.use_smooth=True
        mesh.normals_split_custom_set(vertices[:,3:].tolist())
    else:
        points=[(x-.5,.5-y) for x,y in reversed(profile)];n=len(points)
        vertices=[(x,y,z) for z in (-.5,.5) for x,y in points]
        faces=[tuple(reversed(range(n))),tuple(range(n,2*n))]
        faces.extend((i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n))
        mesh.from_pydata(vertices,[],faces);mesh.update()
    # Match the standard backend's centered bounding box, including profiles
    # whose outline does not use the entire normalized coordinate range.
    coordinates=np.array([tuple(v.co) for v in mesh.vertices])
    centre=(coordinates.min(axis=0)+coordinates.max(axis=0))/2
    for vertex in mesh.vertices:vertex.co-=Vector(centre)
    mesh.update()
    obj=bpy.data.objects.new('Manufactured profile',mesh);bpy.context.collection.objects.link(obj)
    return obj


def procedural_mesh(desc):
    primitive=desc['primitive'];dimensions=desc['dimensions'];centre=desc['center']
    if primitive=='box' and desc.get('cutaway'):
        x,y,z=dimensions;t=max(.004,min(dimensions)*.12)
        specs=[((0,0,-z/2+t/2),(x,y,t)),((-x/2+t/2,0,0),(t,y,z)),
               ((x/2-t/2,0,0),(t,y,z)),((0,-y/2+t/2,0),(x,t,z)),((0,y/2-t/2,0),(x,t,z))]
        pieces=[box_piece(a,b) for a,b in specs]
        bpy.ops.object.select_all(action='DESELECT')
        for item in pieces:item.select_set(True)
        bpy.context.view_layer.objects.active=pieces[0];bpy.ops.object.join()
        obj=bpy.context.object
        # Join leaves one object's offset as its origin; bake it before positioning.
        bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
        obj.location=centre
    else:
        if primitive in ('lathe','extrude'):
            obj=profile_object(desc);bpy.context.view_layer.objects.active=obj;obj.select_set(True)
        elif primitive=='box':bpy.ops.mesh.primitive_cube_add(size=1)
        elif primitive=='cylinder' and not desc.get('cutaway'):
            bpy.ops.mesh.primitive_cylinder_add(vertices=64,radius=.5,depth=1)
        elif primitive=='sphere':bpy.ops.mesh.primitive_uv_sphere_add(segments=40,ring_count=24,radius=.5)
        elif primitive=='ring':bpy.ops.mesh.primitive_torus_add(major_segments=64,minor_segments=16,major_radius=.42,minor_radius=.08)
        else:
            obj=hollow_shell();bpy.context.view_layer.objects.active=obj;obj.select_set(True)
        if primitive not in ('shell','lathe','extrude') and not (primitive=='cylinder' and desc.get('cutaway')):obj=bpy.context.object
        if desc.get('axis')=='x':obj.rotation_euler[1]=math.pi/2
        elif desc.get('axis')=='y':obj.rotation_euler[0]=-math.pi/2
        bpy.context.view_layer.update();obj.dimensions=dimensions;obj.location=centre
    bpy.context.view_layer.objects.active=obj
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True)
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    if primitive in ('box','cylinder','shell','lathe','extrude'):
        bevel=obj.modifiers.new('Manufactured edge radius','BEVEL');bevel.width=min(dimensions)*.055;bevel.segments=3
        bevel.limit_method='ANGLE'
        normal=obj.modifiers.new('Surface normals','WEIGHTED_NORMAL');normal.keep_sharp=True
    for polygon in obj.data.polygons:polygon.use_smooth=primitive not in ('box','extrude')
    return obj


class Worker:
    def __init__(self,root,size,samples):
        self.root=root.resolve();self.meshes={};self.instances={};self.roots={};self.materials={}
        bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
        scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE_NEXT'
        scene.eevee.taa_render_samples=samples
        scene.render.resolution_x,scene.render.resolution_y=size;scene.render.resolution_percentage=100
        scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB'
        scene.render.image_settings.compression=15;scene.render.use_file_extension=False
        scene.render.film_transparent=False;scene.render.threads_mode='FIXED';scene.render.threads=4
        scene.view_settings.view_transform='AgX';scene.view_settings.exposure=-.5
        try:scene.view_settings.look='AgX - Medium High Contrast'
        except (TypeError,ValueError):pass
        scene.world.use_nodes=True
        background=scene.world.node_tree.nodes.get('Background');background.inputs['Color'].default_value=(.18,.22,.30,1)
        background.inputs['Strength'].default_value=.7
        nodes=scene.world.node_tree.nodes;links=scene.world.node_tree.links
        camera_background=nodes.new('ShaderNodeBackground');camera_background.inputs['Color'].default_value=(.008,.013,.025,1)
        light_path=nodes.new('ShaderNodeLightPath');mix=nodes.new('ShaderNodeMixShader')
        links.new(light_path.outputs['Is Camera Ray'],mix.inputs[0]);links.new(background.outputs['Background'],mix.inputs[1])
        links.new(camera_background.outputs['Background'],mix.inputs[2]);links.new(mix.outputs[0],nodes.get('World Output').inputs['Surface'])
        for name,position,power,size in (('Soft key',(-3.5,5,5),950,5),('Fill',(4,2.5,3),650,4),('Rim',(-2,4,-4),1200,3),('Front softbox',(0,1,6),400,5)):
            data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=size
            obj=bpy.data.objects.new(name,data);scene.collection.objects.link(obj)
            obj.location=position;obj.rotation_euler=(-obj.location).to_track_quat('-Z','Y').to_euler()
        camera_data=bpy.data.cameras.new('Portrait camera');self.camera=bpy.data.objects.new('Portrait camera',camera_data)
        scene.collection.objects.link(self.camera);scene.camera=self.camera
        camera_data.sensor_fit='VERTICAL';camera_data.lens=camera_data.sensor_height/(2*math.tan(.78/2));camera_data.clip_start=.01;camera_data.clip_end=500
        bpy.ops.mesh.primitive_plane_add(size=100,rotation=(-math.pi/2,0,0));self.floor=bpy.context.object
        self.floor.name='Studio floor';self.floor.data.materials.append(self.material((.075,.095,.13,4)))

    def path(self,name):
        path=(self.root/name).resolve()
        if not path.is_relative_to(self.root):raise ValueError('Asset path leaves the scene directory')
        return path

    def material(self,value):
        key=tuple(round(float(x),5) for x in value)
        if key in self.materials:return self.materials[key]
        r,g,b,kind=key
        material=bpy.data.materials.new('Surface '+str(len(self.materials)));material.use_nodes=True
        bsdf=material.node_tree.nodes.get('Principled BSDF')
        color=(r,g,b) if .5<kind<=1 else (r**2.2,g**2.2,b**2.2)
        bsdf.inputs['Base Color'].default_value=(*color,1)
        bsdf.inputs['Metallic'].default_value=min(1,max(0,kind))*.45 if kind<=1 else 0
        bsdf.inputs['Roughness'].default_value=.35 if kind>.4 and kind<=1 else .45
        bsdf.inputs['Specular IOR Level'].default_value=.2
        if kind==4:bsdf.inputs['Roughness'].default_value=.8
        if kind==7:
            bsdf.inputs['Emission Color'].default_value=(r,g,b,1);bsdf.inputs['Emission Strength'].default_value=2.5
        elif kind in (8,9):
            bsdf.inputs['Alpha'].default_value=.22 if kind==8 else .35
            bsdf.inputs['Roughness'].default_value=.14
            material.surface_render_method='DITHERED'
        elif .4<kind<=1:
            noise=material.node_tree.nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=175
            bump=material.node_tree.nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.045;bump.inputs['Distance'].default_value=.0003
            material.node_tree.links.new(noise.outputs['Fac'],bump.inputs['Height']);material.node_tree.links.new(bump.outputs['Normal'],bsdf.inputs['Normal'])
        self.materials[key]=material
        return material

    def asset(self,name,data):
        if name in self.meshes:return
        if data.get('procedural'):
            obj=procedural_mesh(data['procedural']);mesh=obj.data
            # Apply geometric modifiers once, then share the evaluated mesh.
            graph=bpy.context.evaluated_depsgraph_get();evaluated=obj.evaluated_get(graph)
            mesh=bpy.data.meshes.new_from_object(evaluated,depsgraph=graph)
            bpy.data.objects.remove(obj,do_unlink=True)
        else:
            with np.load(self.path(data['file']),allow_pickle=False) as archive:vertices=archive['vertices']
            if vertices.ndim!=2 or vertices.shape[1]!=6 or len(vertices)%3 or not np.isfinite(vertices).all():raise ValueError('Invalid triangle mesh')
            mesh=bpy.data.meshes.new(name);mesh.from_pydata(vertices[:,:3].tolist(),[],np.arange(len(vertices)).reshape(-1,3).tolist());mesh.update()
            for polygon in mesh.polygons:polygon.use_smooth=True
            try:mesh.normals_split_custom_set(vertices[:,3:].tolist())
            except (AttributeError,RuntimeError):pass
        self.meshes[name]=mesh

    def frame(self,packet):
        for name,asset in packet.get('assets',{}).items():self.asset(name,asset)
        for obj in self.instances.values():obj.hide_render=True
        groups={}
        for item in packet['objects']:groups.setdefault(item['group'],item['matrix'])
        bindings=packet.get('bindings',{})
        for group in groups:
            if group not in self.roots:
                obj=bpy.data.objects.new(group or 'Scene part',None);bpy.context.scene.collection.objects.link(obj);self.roots[group]=obj
        for group,matrix in groups.items():
            root=self.roots[group];parent=bindings.get(group)
            root.parent=self.roots.get(parent) if parent else None
            root.matrix_parent_inverse=Matrix.Identity(4)
            root.matrix_basis=Matrix.Identity(4) if parent else Matrix(matrix)
        for item in packet['objects']:
            key=item['id'];group=item['group'];pose=Matrix(item['matrix'])
            if key not in self.instances:
                mesh=self.meshes[item['asset']]
                obj=bpy.data.objects.new(key,mesh);bpy.context.scene.collection.objects.link(obj);self.instances[key]=obj
                if not mesh.materials:mesh.materials.append(self.material(item['material']))
                obj.material_slots[0].link='OBJECT'
            obj=self.instances[key];obj.parent=self.roots[group];obj.matrix_parent_inverse=Matrix.Identity(4)
            obj.matrix_basis=Matrix(groups[group]).inverted_safe()@pose
            obj.hide_render=False;obj.material_slots[0].material=self.material(item['material'])
        self.floor.location.y=packet.get('floor',-1.25)+.05;self.floor.hide_render=packet.get('space',False)
        point_camera(self.camera,packet['eye'],packet['focus'])
        bpy.context.scene.render.filepath=str(self.path('frame.png'))
        bpy.ops.render.render(write_still=True)
        reply(state='frame',file='frame.png')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True);parser.add_argument('--width',type=int,required=True);parser.add_argument('--height',type=int,required=True);parser.add_argument('--samples',type=int,default=16)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);worker=Worker(Path(args.root),(args.width,args.height),args.samples)
    reply(state='ready',version=bpy.app.version_string)
    for line in sys.stdin:
        packet=json.loads(line)
        if packet.get('command')=='quit':break
        try:worker.frame(packet)
        except Exception as error:traceback.print_exc();reply(state='error',message=str(error));break


if __name__=='__main__':main()
