import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

import numpy as np
from PIL import Image

from ai_video import validate_generation
from blender_renderer import BlenderRenderer,blender_executable,procedural_description,validate_bindings
from cinematic_render import RendererUnavailable
from mechanism_animation import PALETTE,read_mechanism
from mechanism_3d import Mechanism3D,Mechanism3DShot
from parametric_profiles import read_profile,profile_mesh
from solid_geometry import read_solids,solid_schema


def piece(kind,profile=None):
    item=dict(primitive=kind,center=[.5,.5,.5],size=[.8,.8,.6],axis='z',color='steel')
    if profile is not None:item['profile']=profile
    return item


def part(name,points,parent=''):
    return dict(name=name,shape='plate',color='steel',points=points,pivot=[50,50],parent=parent)


class BlenderBackendTests(unittest.TestCase):
    def test_explicit_missing_blender_path_does_not_silently_select_another_install(self):
        with patch.dict(os.environ,{'BLENDER_PATH':'Z:/missing/blender.exe'}):self.assertIsNone(blender_executable())

    def test_renderer_selection_is_validated_before_planning(self):
        self.assertEqual(validate_generation(dict(prompt='Explain a motor'))['renderer'],'standard')
        with patch('ai_video.blender_executable',return_value=None):
            with self.assertRaisesRegex(ValueError,'unavailable'):validate_generation(dict(prompt='Explain a motor',renderer='blender'))
        with patch('ai_video.blender_executable',return_value='blender'):
            self.assertEqual(validate_generation(dict(prompt='Explain a motor',renderer='blender'))['renderer'],'blender')
        with self.assertRaises(ValueError):validate_generation(dict(prompt='Explain a motor',renderer='arbitrary'))

    def test_rigid_binding_rejects_missing_and_cyclic_parts(self):
        for bindings in ({'A':'missing'},{'A':'B','B':'A'},{'A':'A'}):
            with self.assertRaises(ValueError):validate_bindings(bindings,{'A','B'})

    def test_rigid_child_follows_parent_with_no_duplicate_motion(self):
        data=dict(parts=[part('Rotor',[[30,30],[70,70]]),part('Pointer',[[70,45],[85,55]],'Rotor')],actions=[
            dict(beat=1,part='Rotor',effect='spin',amount=[.3,0],start=.1,end=.5),
            dict(beat=1,part='Pointer',effect='spin',amount=[.3,0],start=.1,end=.5)])
        mechanism=read_mechanism(data,3)
        self.assertEqual(len(mechanism[1]),1)
        model=Mechanism3D(mechanism);model.set_timeline([1,3,3])
        shot=Mechanism3DShot(model,(180,320),1,duration=3.)
        first=shot.at(.5)[0];last=shot.at(2.)[0]
        for objects in (first,last):
            matrices={row[3]:row[2] for row in objects}
            np.testing.assert_allclose(matrices['Rotor'],matrices['Pointer'],atol=1e-8)
        self.assertFalse(np.allclose(first[0][2],last[0][2]))

    def test_child_swept_bounds_include_parent_movement(self):
        data=dict(parts=[part('Platform',[[10,10],[50,20]]),part('Payload',[[80,10],[90,20]],'Platform')],
                  actions=[dict(beat=1,part='Platform',effect='move',amount=[50,0],start=.1,end=.8)])
        with self.assertRaisesRegex(ValueError,'exceeds'):read_mechanism(data,3)
        data['actions'][0]['amount']=[20,0]
        self.assertEqual(len(read_mechanism(data,3)[0]),2)

    def test_conditional_profile_schema_requires_an_outline(self):
        variants=solid_schema(PALETTE)['items']['anyOf']
        self.assertNotIn('profile',variants[0]['required'])
        self.assertIn('profile',variants[1]['required'])
        self.assertEqual(variants[1]['properties']['primitive']['enum'],['lathe','extrude'])

    def test_lathe_builds_a_hollow_part_with_finite_unit_normals(self):
        profile=read_profile([[.6,0],[1,0],[1,1],[.6,1]],'Tube')
        vertices=profile_mesh('lathe',profile)
        self.assertTrue(np.isfinite(vertices).all())
        np.testing.assert_allclose(np.linalg.norm(vertices[:,3:],axis=1),1,atol=1e-6)
        self.assertGreater(np.linalg.norm(vertices[:,:2],axis=1).min(),.29)
        self.assertGreater(np.ptp(vertices[:,2]),.9)

    def test_extrusion_preserves_a_concave_outline(self):
        profile=read_profile([[0,0],[1,0],[1,.3],[.3,.3],[.3,1],[0,1]],'Bracket')
        vertices=profile_mesh('extrude',profile)
        caps=vertices[np.abs(vertices[:,5])>.99].reshape(-1,3,6)
        centers=caps[:,:,:3].mean(axis=1)
        self.assertFalse(np.any((centers[:,0]>-.19999)&(centers[:,1]<.19999)))
        self.assertTrue(np.isfinite(vertices).all())

    def test_invalid_profiles_are_not_repaired_into_invented_shapes(self):
        for value in (None,[[0,0],[1,1],[0,1],[1,0]],[[0,0],[2,0],[1,1]],[[0,0],[1,0],[1,float('nan')]]):
            with self.assertRaises(ValueError):read_profile(value,'Part')

    def test_profile_parts_build_in_the_fast_renderer_too(self):
        profile=[[0,0],[.7,0],[.7,.3],[1,.3],[1,.5],[.6,.5],[.6,1],[0,1]]
        pieces=read_solids([piece('lathe',profile)],'Stepped spindle',PALETTE)
        self.assertEqual(pieces[0].data()['profile'],profile)
        data=dict(parts=[dict(name='Stepped spindle',shape='solid',color='steel',pivot=[50,50],points=[[25,25],[75,75]],geometry=[piece('lathe',profile)])],actions=[])
        model=Mechanism3D(read_mechanism(data,2,require_animation=False))
        self.assertTrue(np.isfinite(model.compiled[0][3]).all())
        description=procedural_description(model.parts[0],0,model.world)
        self.assertEqual(description['primitive'],'lathe');self.assertEqual(description['profile'],profile)

    def test_frame_protocol_preserves_captions_and_cleans_up(self):
        with patch('blender_renderer.blender_executable',return_value='fake'):
            renderer=BlenderRenderer((64,64));root=renderer.root
        vertices=np.array([[0,0,0,0,0,1],[1,0,0,0,0,1],[0,1,0,0,0,1]],dtype=float)
        renderer.register_mesh('triangle',vertices);Image.new('RGB',(64,64),'black').save(root/'frame.png')
        stream=io.StringIO();renderer.process=Mock(stdin=stream,stdout=None);renderer.process.poll.return_value=0
        shot=SimpleNamespace(at=lambda *args:([('triangle',(.5,.5,.5,.5),np.eye(4),'Part')],(0,0,5),(0,0,0)),subject='mechanism-3d',caption=None)
        renderer.events.put(dict(state='frame'))
        with patch.object(renderer,'_start'):
            frame=renderer.frame(shot,0,subtitle=(Image.new('RGBA',(10,10),'red'),(4,4)))
        self.assertEqual(frame.getpixel((6,6)),(255,0,0))
        packet=json.loads(stream.getvalue());self.assertEqual(packet['objects'][0]['group'],'Part')
        self.assertTrue(packet['assets']['triangle']['file'].endswith('.npz'))
        renderer.close();self.assertFalse(root.exists())

    def test_rotation_axis_matches_the_actual_shaft(self):
        data=dict(parts=[dict(name='Spindle',shape='solid',color='steel',pivot=[50,50],points=[[30,20],[70,80]],rotation_axis='y',
                              geometry=[{**piece('lathe',[[0,0],[1,0],[1,1],[0,1]]),'axis':'y'}])],
                  actions=[dict(beat=1,part='Spindle',effect='spin',amount=[.3,0],start=.1,end=.5)])
        model=Mechanism3D(read_mechanism(data,3));model.set_timeline([1,3,3])
        matrix=Mechanism3DShot(model,(180,320),1,duration=3.).at(2.)[0][0][2]
        np.testing.assert_allclose(matrix[1],(0,1,0,0),atol=1e-8)
        self.assertFalse(np.allclose(matrix,np.eye(4)))
        desc=procedural_description(model.parts[0],0,model.world)
        self.assertAlmostEqual(desc['dimensions'][0],desc['dimensions'][2])

    def test_local_schema_compaction_preserves_the_geometry_contract(self):
        from planning_json import compact_local_schema
        from mechanism_planner import _geometry_schema
        from mechanism_animation import SHAPES
        inv=dict(components=[dict(name='A',shape='solid'),dict(name='B',shape='solid')])
        original=_geometry_schema(3,SHAPES,inv);compact=compact_local_schema(original)
        self.assertIn('$defs',compact)
        for item in compact['properties']['parts']['items']['anyOf']:
            self.assertEqual(item['properties']['geometry'],{'$ref':'#/$defs/solidGeometry'})
        self.assertEqual(compact['$defs']['solidGeometry'],original['properties']['parts']['items']['anyOf'][0]['properties']['geometry'])
        self.assertLess(len(json.dumps(compact)),len(json.dumps(original)))

    def test_timeout_stops_the_worker_and_removes_temporary_assets(self):
        with patch('blender_renderer.blender_executable',return_value='fake'):renderer=BlenderRenderer((64,64),timeout=.001)
        root=renderer.root
        with self.assertRaisesRegex(RendererUnavailable,'time limit'):renderer._event()
        self.assertTrue(renderer.closed);self.assertFalse(root.exists())


    def test_worker_failure_can_finish_the_same_frame_with_standard_rendering(self):
        fallback=Mock();expected=Image.new('RGB',(64,64),'red');fallback.frame.return_value=expected
        with patch('blender_renderer.blender_executable',return_value='fake'):
            renderer=BlenderRenderer((64,64),fallback=True)
        root=renderer.root
        vertices=np.array([[0,0,0,0,0,1],[1,0,0,0,0,1],[0,1,0,0,0,1]],dtype=float)
        renderer.register_mesh('Part',vertices)
        shot=Mock();subtitle=(Image.new('RGBA',(4,4),'red'),(0,0))
        with patch.object(renderer,'_blender_frame',side_effect=RendererUnavailable('GPU failed')) as original,patch('blender_renderer.CinematicRenderer',return_value=fallback):
            self.assertIs(renderer.frame(shot,1.5,None,subtitle),expected)
            self.assertIs(renderer.frame(shot,1.6,None,subtitle),expected)
        self.assertEqual(original.call_count,1)
        self.assertEqual(renderer.backend,'standard');self.assertIn('Standard',renderer.warning)
        self.assertFalse(root.exists());fallback.register_mesh.assert_called_once()
        self.assertEqual(fallback.frame.call_args.args,(shot,1.6,None,subtitle))
        renderer.close();fallback.close.assert_called_once()

    def test_strict_blender_preview_does_not_disguise_a_failed_benchmark(self):
        with patch('blender_renderer.blender_executable',return_value='fake'):renderer=BlenderRenderer((64,64))
        with renderer,patch.object(renderer,'_blender_frame',side_effect=RendererUnavailable('GPU failed')):
            with self.assertRaisesRegex(RendererUnavailable,'GPU failed'):renderer.frame(Mock(),0)


    def test_blender_setup_unloads_only_the_studios_own_models(self):
        from ai_video import release_render_model_memory,OLLAMA_MODEL
        response=Mock();response.json.return_value={'models':[{'name':OLLAMA_MODEL},{'name':'another-app-model'}]}
        with patch.dict(os.environ,{'AI_VIDEO_GEMINI_API_KEY':''}),patch('ai_video.requests.get',return_value=response),patch('ai_video.requests.post') as post:
            release_render_model_memory()
        post.assert_called_once()
        self.assertEqual(post.call_args.kwargs['json'],dict(model=OLLAMA_MODEL,keep_alive=0,stream=False))


if __name__=='__main__':unittest.main()
