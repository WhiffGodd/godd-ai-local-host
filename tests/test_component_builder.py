import copy
import unittest
from unittest.mock import Mock

import numpy as np

from mechanism_animation import PALETTE, _electrical_shape, read_mechanism
from mechanism_planner import _inventory, _inventory_geometry, _parts_data, parts_schema, plan_custom_mechanism, terminal_port
from mechanism_animation import SHAPES
from connection_routing import route_wire
from mechanism_dynamics import conducting_wires
from mechanism_3d import Mechanism3D, Mechanism3DShot


def component(name,shape,points):
    return dict(name=name,shape=shape,color='steel',pivot=[sum(v)/2 for v in zip(*points)],points=points)


def piece(kind,center,size,color='steel',axis='z'):
    return dict(primitive=kind,center=center,size=size,axis=axis,color=color)


class ComponentBuilderTests(unittest.TestCase):
    def test_terminal_names_normalize_without_changing_polarity(self):
        for value,shape,expected in (('terminal_left','coil','left'),('right terminal','motor','right'),
                                     ('+','battery','positive'),('-','battery','negative'),('bottom','battery','negative'),
                                     ('positive terminal','solid','left')):
            self.assertEqual(terminal_port(value,shape),expected)

    def circuit(self):
        return dict(parts=[component('Battery','battery',[[10,25],[20,75]]),
                           component('Coil','coil',[[55,35],[85,65]])],connections=[
            dict(name='Feed',color='red',points=[[15,25],[15,15],[55,15],[55,50]],links=['Battery:positive','Coil:left']),
            dict(name='Return',color='blue',points=[[85,50],[90,85],[15,85],[15,75]],links=['Coil:right','Battery:negative'])])

    def test_component_schema_never_accepts_wire_metadata(self):
        schema=parts_schema(5,['plate','solid','coil','wire','battery'])
        self.assertIn('connections',schema['required'])
        for item in schema['properties']['parts']['items']['anyOf']:
            self.assertFalse(item['additionalProperties'])
            self.assertNotIn('links',item['properties'])
            self.assertNotIn('wire',item['properties']['shape'].get('enum',[]))
        connection=schema['properties']['connections']['items']
        self.assertEqual(connection['properties']['links']['minItems'],2)
        self.assertEqual(connection['properties']['links']['maxItems'],2)

    def test_coil_and_external_connections_compile_to_different_parts(self):
        raw=self.circuit();parts=_parts_data(raw,4)
        self.assertEqual({p['name']:p['shape'] for p in parts},dict(Battery='battery',Coil='coil',Feed='wire',Return='wire'))
        coil=next(p for p in parts if p['name']=='Coil')
        self.assertFalse(coil['links'])
        feed=next(p for p in parts if p['name']=='Feed')
        self.assertEqual(feed['links'],[['Battery','positive'],['Coil','left']])
        self.assertEqual(feed['points'][-1],[55,50])
        self.assertEqual(len(raw['parts']),2)

    def inventory(self):
        raw=self.circuit()
        return dict(components=[dict(name=p['name'],shape=p['shape'],function='Functional electrical part',motion='state') for p in raw['parts']],
                    connections=[{k:v for k,v in w.items() if k!='points'} for w in raw['connections']])

    def test_inventory_rejects_unknown_references_before_geometry_is_requested(self):
        data=self.inventory();data['connections'][0]['links'][1]='Missing:left'
        with self.assertRaisesRegex(ValueError,'missing from components'):_inventory(data,SHAPES)
        data=self.inventory();data['connections'].pop()
        with self.assertRaisesRegex(ValueError,'incomplete'):_inventory(data,SHAPES)

    def test_inventory_preserves_subpart_identity_and_repairs_wire_name_collisions(self):
        data=self.inventory()
        data['connections'][0]['name']='Coil'
        data['components'].extend([dict(name='Fixed housing',shape='capacitor',function='Casing',motion='fixed'),
                                   dict(name='Stator magnets',shape='motor',function='Magnets',motion='fixed')])
        inv=_inventory(data,SHAPES)
        self.assertEqual({p['name']:p['shape'] for p in inv['components']}['Fixed housing'],'solid')
        self.assertEqual({p['name']:p['shape'] for p in inv['components']}['Stator magnets'],'solid')
        self.assertNotEqual(inv['connections'][0]['name'],'Coil')
        self.assertEqual(inv['connections'][0]['links'],data['connections'][0]['links'])

    def test_router_avoids_obstacles_and_keeps_both_declared_terminals(self):
        path=route_wire([15,25],[55,50],'positive','left',[[[10,25],[20,75]],[[55,35],[85,65]],[[30,10],[40,40]]])
        self.assertEqual(path[0],[15,25]);self.assertEqual(path[-1],[55,50])
        for a,b in zip(path,path[1:]):
            self.assertTrue(a[0]==b[0] or a[1]==b[1])
            middle=np.mean([a,b],axis=0)
            self.assertFalse(30<middle[0]<40 and 10<middle[1]<40)

    def test_fixed_inventory_drives_geometry_and_connections_then_actions(self):
        inv=self.inventory();geometry={'parts':self.circuit()['parts']}
        actions={'actions':[dict(beat=1,part='Coil',effect='energize',amount=[1,0],start=.1,end=.8)]}
        request=Mock(side_effect=[inv,geometry,actions])
        parts,events=plan_custom_mechanism('Explain a battery and coil',[dict(narration='Hook'),dict(narration='Current creates a field')],request,None,'small')
        self.assertEqual([next(iter(c.args[2]['properties'])) for c in request.call_args_list],['components','parts','actions'])
        variants=request.call_args_list[1].args[2]['properties']['parts']['items']['anyOf']
        self.assertEqual({v['properties']['name']['const'] for v in variants},{'Battery','Coil'})
        self.assertEqual({p.part.label for p in parts},{'Battery','Coil','Feed','Return'})
        self.assertEqual(events[0].effect,'energize')
        self.assertTrue(all(len(p.links)==2 for p in parts if p.shape=='wire'))

    def test_custom_sources_and_loads_connect_without_a_device_template(self):
        inv=self.inventory()
        inv['components'][0].update(name='Power supply',shape='solid',electrical_role='source')
        inv['components'][1].update(name='Custom sensor',shape='solid',electrical_role='load')
        inv['connections'][0]['links']=['Power supply:left','Custom sensor:left']
        inv['connections'][1]['links']=['Custom sensor:right','Power supply:right']
        inv=_inventory(inv,SHAPES)
        source=self.solid();source.update(name='Power supply',points=[[10,20],[25,70]],pivot=[17.5,45])
        load=self.solid();load.update(name='Custom sensor',points=[[60,30],[85,60]],pivot=[72.5,45])
        data=_inventory_geometry(dict(parts=[source,load]),4,inv)
        parts,_=read_mechanism(dict(parts=data,actions=[]),4,require_animation=False)
        self.assertEqual(conducting_wires(parts,{}),{'Feed','Return'})
        self.assertEqual(next(p for p in parts if p.part.label=='Power supply').electrical_role,'source')

    def test_cutaway_parent_envelope_does_not_block_its_internal_terminals(self):
        inv=self.inventory()
        inv['components'][0].update(name='Power supply',shape='solid',electrical_role='source')
        inv['components'][1].update(name='Internal sensor',shape='solid',electrical_role='load')
        inv['connections'][0]['links']=['Power supply:left','Internal sensor:left']
        inv['connections'][1]['links']=['Internal sensor:right','Power supply:right']
        source=self.solid();source.update(name='Power supply',points=[[10,10],[90,90]],pivot=[50,50])
        load=self.solid();load.update(name='Internal sensor',points=[[40,35],[60,65]],pivot=[50,50])
        parts=_inventory_geometry(dict(parts=[source,load]),4,_inventory(inv,SHAPES))
        self.assertEqual(len(parts),4)
        self.assertTrue(all(len(p['links'])==2 for p in parts if p['shape']=='wire'))

    def test_legacy_conductor_named_coil_stays_a_conductor(self):
        self.assertEqual(_electrical_shape('Coil','wire'),'wire')
        self.assertEqual(_electrical_shape('Motor rotor','solid'),'solid')

    def test_invalid_component_metadata_gets_component_specific_repair(self):
        raw=self.circuit();raw['parts'][1]['links']=['Battery:positive']
        with self.assertRaisesRegex(ValueError,'Coil is a physical coil.*top-level connections'):_parts_data(raw,4)

    def solid(self):
        data=component('Flanged spindle','solid',[[25,25],[75,75]])
        data['geometry']=[piece('cylinder',[.5,.5,.5],[.2,.2,1]),
                          piece('ring',[.5,.5,.25],[.8,.8,.15],'gold')]
        return data

    def test_unfamiliar_part_preserves_geometry_and_builds_curved_solid_meshes(self):
        data=self.solid();parts=_parts_data(dict(parts=[data]),3)
        self.assertEqual(parts[0]['geometry'],data['geometry'])
        actions=[dict(beat=1,part='Flanged spindle',effect='turn',amount=[90,0],start=.1,end=.8)]
        model=Mechanism3D(read_mechanism(dict(parts=parts,actions=actions),3))
        self.assertEqual(len(model.compiled),2)
        for _,_,_,vertices,_,_ in model.compiled:
            self.assertTrue(np.isfinite(vertices).all())
            self.assertGreater(np.ptp(vertices[:,2]),0)
            np.testing.assert_allclose(np.linalg.norm(vertices[:,3:],axis=1),1,atol=1e-5)
        before=Mechanism3DShot(model,(180,320),1,duration=3.).at(0)[0]
        after=Mechanism3DShot(model,(180,320),1,duration=3.).at(2.9)[0]
        self.assertEqual(len(before),2)
        for a,b in zip(before,after):self.assertFalse(np.allclose(a[2],b[2]))
        np.testing.assert_allclose(before[0][2],before[1][2])
        np.testing.assert_allclose(after[0][2],after[1][2])

    def test_unsupported_or_outside_geometry_is_rejected_with_its_field(self):
        for field,value,pattern in (('center',[.95,.5,.5],'outside'),('size',[0,.3,.3],'size'),
                                    ('axis','w','axis'),('primitive','unknown','primitive')):
            with self.subTest(field=field):
                data=self.solid();data['geometry'][0][field]=value
                with self.assertRaisesRegex(ValueError,pattern):read_mechanism(dict(parts=[data],actions=[]),3,require_animation=False)

    def test_generated_compound_is_fitted_as_one_group_and_surfaces_get_thickness(self):
        data=self.solid()
        for p in data['geometry']:
            p['center']=[x*10-20 for x in p['center']]
            p['size']=[x*10 for x in p['size']]
        data['geometry'][1]['size'][2]=0
        parts=_parts_data(dict(parts=[data]),3)
        model=Mechanism3D(read_mechanism(dict(parts=parts,actions=[]),3,require_animation=False))
        self.assertEqual(len(model.compiled),2)
        self.assertTrue(all(np.isfinite(row[3]).all() for row in model.compiled))
        geometry=parts[0]['geometry']
        self.assertGreater(geometry[0]['center'][2],geometry[1]['center'][2])
        self.assertAlmostEqual(geometry[0]['size'][0]/geometry[1]['size'][0],.25)

    def test_continuous_spin_persists_across_narration_cuts(self):
        data=self.solid()
        events=[dict(beat=1,part=data['name'],effect='spin',amount=[.3,0],start=.1,end=.5)]
        model=Mechanism3D(read_mechanism(dict(parts=[data],actions=events),4))
        model.set_timeline([2,3,5,2])
        end=Mechanism3DShot(model,(180,320),1,duration=3.).at(3.)[0]
        start=Mechanism3DShot(model,(180,320),2,duration=5.).at(0.)[0]
        later=Mechanism3DShot(model,(180,320),2,duration=5.).at(1.)[0]
        for a,b,c in zip(end,start,later):
            np.testing.assert_allclose(a[2],b[2],atol=1e-8)
            self.assertFalse(np.allclose(b[2],c[2]))

    def test_generic_housing_is_opened_to_reveal_the_mechanism(self):
        data=self.solid();data['geometry']=[piece('box',[.5,.5,.5],[.8,.8,.3])]
        def vertices(name):
            item=copy.deepcopy(data);item['name']=name
            return Mechanism3D(read_mechanism(dict(parts=[item],actions=[]),3,require_animation=False)).compiled[0][3]
        self.assertLess(len(vertices('Fixed housing')),len(vertices('Support block')))

    def test_continuous_rotation_prompt_repairs_small_finite_turns(self):
        inv=dict(components=[dict(name='Rotor',shape='gear',function='Rotates',motion='rotate')])
        geometry=dict(parts=[component('Rotor','gear',[[25,25],[75,75]])])
        def actions(effect,amount):return dict(actions=[dict(beat=1,part='Rotor',effect=effect,amount=amount,start=.1,end=.8)])
        request=Mock(side_effect=[inv,geometry,actions('turn',[5,0]),actions('spin',[.5,0])])
        result=plan_custom_mechanism('Show a rotor turning continuously',[dict(narration='Hook'),dict(narration='The rotor spins')],request,None,'small')
        self.assertEqual(result[1][0].effect,'spin')
        self.assertIn('continuous rotation',request.call_args_list[-1].args[1])


if __name__=='__main__':unittest.main()
