import copy
import json
import unittest
from unittest.mock import Mock

import numpy as np

from mechanism_animation import Action, read_mechanism
from mechanism_3d import Mechanism3D, Mechanism3DShot
from mechanism_dynamics import CurrentTrack, conducting_wires
from mechanism_planner import _finish_actions, _parts_data, actions_schema, parts_schema, plan_custom_mechanism
from planning_json import planning_json


def part(name,shape,points,links=None):
    return dict(name=name,shape=shape,color='steel',pivot=[sum(v)/len(v) for v in zip(*points)],points=points,links=links or [])


def action(name,effect,amount,beat=1):
    return dict(part=name,effect=effect,amount=amount,beat=beat,start=.1,end=.8)


def circuit():
    parts=[part('Battery','battery',[[10,30],[20,70]]),
           part('Switch','switch',[[35,20],[55,30]]),
           part('Capacitor','capacitor',[[70,40],[85,70]])]
    for name,links,points in (
        ('Feed',['Battery:positive','Switch:left'],[[15,30],[15,25],[35,25]]),
        ('Charge wire',['Switch:right','Capacitor:left'],[[55,25],[70,25],[70,55]]),
        ('Return',['Capacitor:right','Battery:negative'],[[85,55],[90,80],[15,80],[15,70]])):
        parts.append(part(name,'wire',points,links))
    return parts


class UniversalPlannerTests(unittest.TestCase):
    def test_schema_bounds_geometry_separately_from_signed_motion(self):
        for variant in parts_schema(4,['plate','wire'])['properties']['parts']['items']['anyOf']:
            for pair in (variant['properties']['pivot'],variant['properties']['points']['items']):
                self.assertEqual(pair['items'],dict(type='number',minimum=0,maximum=100))
        amount=actions_schema(4,[part('Gate','plate',[[10,10],[90,20]])])['properties']['actions']['items']['anyOf'][0]['properties']['amount']
        self.assertEqual(amount['items']['minimum'],-720)

    def test_whole_layout_is_fitted_without_clipping_or_changing_joints(self):
        raw={'parts':[part('Support','plate',[[-100,-30],[100,-10]]),
                      part('Link','pipe',[[100,-10],[200,50]])]}
        raw['parts'][1]['pivot']=[100,-10]
        valid=_parts_data(raw,4)
        self.assertEqual(valid[0]['points'][-1],valid[1]['points'][0])
        self.assertEqual(valid[1]['pivot'],valid[1]['points'][0])
        a,b=valid[0]['points'];c,d=valid[1]['points']
        self.assertAlmostEqual((b[0]-a[0])/(d[0]-c[0]),2)
        self.assertAlmostEqual((b[1]-a[1])/(d[1]-c[1]),1/3)
        for item in valid:
            self.assertTrue(all(0<=v<=100 for pair in [item['pivot'],*item['points']] for v in pair))
        self.assertEqual(raw['parts'][0]['points'][0],[-100,-30])

    def test_numeric_strings_recover_but_invalid_coordinates_name_the_field(self):
        raw={'parts':[part('Guide','plate',[[10,20],[90,25]])]}
        raw['parts'][0]['points']=[['10','20'],['90','25']]
        raw['parts'][0]['pivot']=['50','22.5']
        self.assertEqual(_parts_data(raw,4)[0]['pivot'],[50,22.5])
        for bad in ([10,float('nan')],[True,20],[10,float('inf')],[10,20,30],[10],[10,'bad'],[10,10**1000]):
            with self.subTest(bad=str(bad)[:50]):
                invalid=copy.deepcopy(raw);invalid['parts'][0]['points'][0]=bad
                with self.assertRaisesRegex(ValueError,r'Guide.points\[0\]'):_parts_data(invalid,4)

    def test_coordinate_error_gives_repair_the_part_and_field_then_succeeds(self):
        bad={'parts':[part('Guide','plate',[[10,20,30],[90,25]])]}
        good={'parts':[part('Guide','plate',[[10,20],[90,25]])]}
        request=Mock(side_effect=[bad,good,{'actions':[action('Guide','move',[0,10])]}])
        result=plan_custom_mechanism('Move a guide',[dict(narration='Hook'),dict(narration='Move')],request,None,'small')
        self.assertIn('Guide.points[0]',request.call_args_list[1].args[1])
        self.assertEqual(len(result[1]),1)

    def test_wrapped_json_is_accepted_but_truncated_nested_plan_is_rejected(self):
        for value in ('```json\n{"parts":[]}\n```','Here is the plan: {"parts":[]}'):
            self.assertEqual(planning_json(value),{'parts':[]})
        for value in ('{"parts":[{"name":"nested"}', '{"a":1} {"b":2}', '[]'):
            with self.assertRaises(ValueError):planning_json(value)

    def test_same_staged_path_accepts_mechanical_and_biological_topics(self):
        for prompt,shape,name,effect,amount in (
            ('Explain a rotating cam','gear','Cam','turn',[180,0]),
            ('Explain a neuron signal','neuron','Neuron','flow',[1,0])):
            with self.subTest(prompt=prompt):
                geometry={'parts':[part(name,shape,[[10,25],[90,70]])]}
                request=Mock(side_effect=[json.dumps(geometry),json.dumps({'actions':[action(name,effect,amount)]})])
                result=plan_custom_mechanism(prompt,[{'narration':'Hook'},{'narration':prompt}],request,None,'small')
                self.assertEqual(len(result[1]),1)
                self.assertEqual(list(request.call_args_list[0].args[2]['properties']),['components'])
                schema=request.call_args_list[1].args[2]
                variants=schema['properties']['actions']['items']['anyOf']
                self.assertEqual([v['properties']['part']['const'] for v in variants],[name])
                self.assertEqual([c.args[-1] for c in request.call_args_list],['small','small'])

    def test_action_repair_keeps_validated_geometry_and_reports_the_specific_error(self):
        geometry={'parts':[part('Cam','gear',[[10,20],[90,80]])]}
        bad=action('Cam','turn',[90,0]);bad['end']=bad['start']
        request=Mock(side_effect=[geometry,{'actions':[bad]},{'actions':[action('Cam','turn',[90,0])]}])
        result=plan_custom_mechanism('Rotate a cam',[{'narration':'Hook'},{'narration':'Turn'}],request,None,'small')
        self.assertEqual(len(result[1]),1)
        self.assertEqual([list(c.args[2]['properties']) for c in request.call_args_list],[['components'],['actions'],['actions']])
        self.assertIn('start < end',request.call_args_list[2].args[1])
        self.assertIn('"Cam"',request.call_args_list[2].args[0])

    def test_one_persistent_motion_is_valid_but_zero_placeholders_are_not(self):
        data={'parts':[part('Cam','gear',[[10,20],[90,80]])],'actions':[action('Cam','turn',[180,0])]}
        self.assertEqual(len(read_mechanism(data,6)[1]),1)
        data['actions'][0]['amount']=[0,0]
        with self.assertRaisesRegex(ValueError,'nonzero'):read_mechanism(data,6)

    def test_edge_on_plate_gets_thickness_without_inventing_a_gear_size(self):
        raw={'parts':[part('Guide','plate',[[10,70],[90,70]])]}
        valid=_parts_data(raw,4)
        self.assertEqual(valid[0]['points'],[[10,69],[90,71]])
        self.assertEqual(raw['parts'][0]['points'],[[10,70],[90,70]])
        raw['parts'][0]['shape']='gear'
        with self.assertRaisesRegex(ValueError,'width and height'):_parts_data(raw,4)

    def test_named_components_cannot_silently_become_another_native_shape(self):
        parts=circuit();parts[0]['shape']='capacitor';parts[1]['shape']='capacitor'
        valid=_parts_data({'parts':parts},4)
        self.assertEqual([p['shape'] for p in valid[:3]],['battery','switch','capacitor'])

    def test_wire_links_snap_to_ports_and_broken_topology_is_rejected(self):
        parts=circuit();parts[3]['points'][0]=[1,1]
        valid=_parts_data({'parts':parts},4)
        self.assertEqual(valid[3]['points'][0],[15,30])
        components,_=read_mechanism({'parts':valid,'actions':[]},4,require_animation=False)
        self.assertFalse(conducting_wires(components,{'switch':False}))
        self.assertEqual(conducting_wires(components,{'switch':True}),{'Feed','Charge wire','Return'})
        parts[-1]['links']=['Capacitor:right','Battery:positive']
        with self.assertRaisesRegex(ValueError,'incomplete'):_parts_data({'parts':parts},4)

    def test_current_phase_remains_continuous_when_current_decreases(self):
        events=[Action(1,'Wire','current',(1,0),.1,.8),Action(2,'Wire','current',(.2,0),.1,.8)]
        track=CurrentTrack(events,[2,4,5])
        boundary=6+.1*5
        self.assertAlmostEqual(track.area(boundary-1e-7),track.area(boundary+1e-7),places=5)
        self.assertAlmostEqual(track.level(10.5),.2)
        self.assertGreater(track.area(11),track.area(10))
        self.assertLess(track.area(11)-track.area(10),track.area(6)-track.area(5))

    def test_verified_series_loop_applies_one_current_to_all_wires(self):
        parts=_parts_data({'parts':circuit()},4)
        parts,events=_finish_actions(parts,[action('Switch','switch',[1,0]),action('Feed','current',[.6,0],2)],4)
        self.assertEqual({a.part for a in events if a.effect=='current'},{'Feed','Charge wire','Return'})
        with self.assertRaisesRegex(ValueError,'Conflicting'):
            _finish_actions(_parts_data({'parts':circuit()},4),[action('Feed','current',[1,0]),action('Return','current',[-1,0])],4)

    def test_only_switch_blade_moves_and_open_switch_blocks_flow(self):
        parts=_parts_data({'parts':circuit()},4)
        events=[action('Switch','switch',[1,0],2),action('Feed','current',[1,0]),action('Charge wire','flow',[1,0])]
        model=Mechanism3D(read_mechanism({'parts':parts,'actions':events},4))
        shot=Mechanism3DShot(model,(180,320),1,duration=3.)
        self.assertFalse([o for o in shot.at(2)[0] if o[0]=='sphere'])
        first=Mechanism3DShot(model,(180,320),1,duration=3.).at(2)[0]
        last=Mechanism3DShot(model,(180,320),2,duration=3.).at(3)[0]
        a={o[0]:o[2] for o in first if o[3]=='Switch'}
        b={o[0]:o[2] for o in last if o[3]=='Switch'}
        for name in a:
            if model.roles[name]=='switch_blade':self.assertFalse(np.allclose(a[name],b[name]))
            else:np.testing.assert_allclose(a[name],b[name])
        self.assertTrue([o for o in last if o[0]=='sphere'])


if __name__=='__main__':unittest.main()
