import copy
import unittest
import json
from unittest.mock import patch
from unittest.mock import Mock

from circuit_inventory import CircuitInventoryError, inventory_graph
from mechanism_animation import SHAPES, read_mechanism
from mechanism_dynamics import conducting_wires
from mechanism_planner import _inventory, _wiring_schema, plan_custom_mechanism


def component(name,shape,role='none'):
    return dict(name=name,shape=shape,function='Electrical component' if shape!='spring' else 'Mechanical return spring',motion='fixed',electrical_role=role)


def connection(name,a,b):return dict(name=name,color='red',links=[a,b])


def solenoid():
    return dict(components=[component('Battery','battery'),component('Switch','switch'),component('Coil','coil'),component('Return spring','spring')],
                connections=[connection('Feed','Battery:positive','Switch:left'),connection('Switched lead','Switch:right','Coil:left'),
                             connection('Return','Coil:right','Battery:negative')])


class CircuitInventoryTests(unittest.TestCase):
    def test_missing_series_return_is_completed_without_changing_declared_wires(self):
        raw=solenoid();raw['connections'].pop();original=copy.deepcopy(raw)
        inv=_inventory(raw,SHAPES)
        self.assertEqual(raw,original)
        self.assertEqual(inv['connections'][:2],original['connections'])
        self.assertEqual(set(inv['connections'][-1]['links']),{'Battery:negative','Coil:right'})
        graph=inventory_graph(inv['components'],inv['connections'])
        self.assertFalse(conducting_wires(graph,{'switch':False}))
        self.assertEqual(conducting_wires(graph,{'switch':True}),{w['name'] for w in inv['connections']})

    def test_missing_feed_or_middle_connection_can_also_be_completed(self):
        for index in (0,1):
            raw=solenoid();missing=raw['connections'].pop(index)
            inv=_inventory(raw,SHAPES)
            self.assertEqual(set(inv['connections'][-1]['links']),set(missing['links']))

    def test_same_fix_applies_to_capacitor_led_resistor_and_custom_load(self):
        for shape in ('capacitor','led','resistor','motor','solid'):
            raw=solenoid();raw['components'][2]=component('Load',shape,'load' if shape=='solid' else 'none')
            raw['connections'][1]['links'][1]='Load:left';raw['connections'].pop()
            inv=_inventory(raw,SHAPES)
            self.assertEqual(set(inv['connections'][-1]['links']),{'Battery:negative','Load:right'})

    def test_custom_source_keeps_its_return_terminal(self):
        raw=solenoid();raw['components'][0]=component('Power supply','solid','source')
        raw['connections'][0]['links'][0]='Power supply:left';raw['connections'].pop()
        inv=_inventory(raw,SHAPES)
        self.assertEqual(set(inv['connections'][-1]['links']),{'Power supply:right','Coil:right'})

    def test_complete_parallel_branches_are_preserved(self):
        raw=dict(components=[component('Battery','battery'),component('A','resistor'),component('B','led')],connections=[
            connection('A feed','Battery:positive','A:left'),connection('A return','A:right','Battery:negative'),
            connection('B feed','Battery:positive','B:left'),connection('B return','B:right','Battery:negative')])
        self.assertEqual(_inventory(raw,SHAPES)['connections'],raw['connections'])

    def test_ambiguous_gaps_report_exact_ports_and_keep_components(self):
        raw=solenoid();raw['connections']=raw['connections'][:1];raw['components'].append(component('Extra resistor','resistor'))
        with self.assertRaises(CircuitInventoryError) as caught:_inventory(raw,SHAPES)
        self.assertIn('Battery:negative',str(caught.exception))
        self.assertIn('Coil:right',str(caught.exception))
        self.assertIn('Feed',str(caught.exception))
        self.assertEqual([p['name'] for p in caught.exception.inventory['components']],[p['name'] for p in raw['components']])

    def test_simple_wrong_polarity_gets_a_verified_series_return(self):
        raw=solenoid();raw['connections'][-1]['links'][-1]='Battery:positive'
        inv=_inventory(raw,SHAPES)
        self.assertEqual(inv['connections'][-1]['links'],['Coil:right','Battery:negative'])

    def test_multiple_sources_are_not_guessed(self):
        raw=solenoid();raw['components'].append(component('Other battery','battery'));raw['connections'].pop()
        with self.assertRaises(CircuitInventoryError):_inventory(raw,SHAPES)

    def test_repair_never_bypasses_a_floating_load_or_switch(self):
        raw=solenoid();raw['components'].append(component('Extra resistor','resistor'));raw['connections'].pop()
        with self.assertRaises(CircuitInventoryError):_inventory(raw,SHAPES)

    def test_wire_names_stay_unique_when_completing_the_gap(self):
        raw=solenoid();raw['connections'].pop();raw['connections'][0]['name']='Circuit return'
        inv=_inventory(raw,SHAPES)
        self.assertEqual(len({w['name'].casefold() for w in inv['connections']}),3)

    def test_metal_rod_and_return_spring_do_not_gain_circuit_ports(self):
        raw=solenoid()
        raw['components'].extend([
            dict(name='Iron rod',shape='solid',function='Sliding ferromagnetic core pulled into the coil',motion='slide',electrical_role='conductor'),
            dict(name='Spring casing',shape='solid',function='Holds the mechanical return spring',motion='fixed',electrical_role='none')])
        inv=_inventory(raw,SHAPES)
        rod=next(p for p in inv['components'] if p['name']=='Iron rod')
        self.assertEqual(rod['electrical_role'],'')
        inv['connections'][-1]['links'][1]='Spring casing:left'
        from mechanism_planner import _inventory_connections
        repaired=_inventory_connections(inv['components'],inv['connections'])
        self.assertTrue(all(not any('Spring casing:' in ref for ref in w['links']) for w in repaired['connections']))
        allowed=_wiring_schema(repaired)['properties']['connections']['items']['properties']['links']['items']['enum']
        self.assertNotIn('Iron rod:left',allowed)
        self.assertNotIn('Spring casing:left',allowed)

    def test_a_moving_electrical_contact_can_still_carry_current(self):
        raw=solenoid()
        raw['components'][2]=dict(name='Sliding contact rod',shape='solid',function='Carries current between electrical contacts',motion='slide',electrical_role='conductor')
        raw['connections'][1]['links'][1]='Sliding contact rod:left'
        raw['connections'][2]['links'][0]='Sliding contact rod:right'
        inv=_inventory(raw,SHAPES)
        self.assertEqual(inv['components'][2]['electrical_role'],'conductor')

    def test_wiring_only_retry_preserves_validated_components_and_routes_them(self):
        good=solenoid();good['components'].append(component('Resistor','resistor'))
        good['connections'][-1]['links'][1]='Resistor:left'
        good['connections'].append(connection('Load return','Resistor:right','Battery:negative'))
        bad=copy.deepcopy(good);bad['connections']=[connection('Wrong','Switch:left','Coil:left')]
        geometry=dict(parts=[
            dict(name='Battery',shape='battery',color='steel',pivot=[15,50],points=[[10,30],[20,70]]),
            dict(name='Switch',shape='switch',color='steel',pivot=[45,20],points=[[35,15],[55,25]]),
            dict(name='Coil',shape='coil',color='steel',pivot=[75,50],points=[[65,40],[85,60]]),
            dict(name='Return spring',shape='spring',color='steel',pivot=[45,75],points=[[35,75],[55,75]]),
            dict(name='Resistor',shape='resistor',color='steel',pivot=[75,80],points=[[65,75],[85,85]])])
        actions=dict(actions=[dict(beat=1,part='Switch',effect='switch',amount=[1,0],start=.1,end=.2),
                              dict(beat=2,part='Feed',effect='current',amount=[1,0],start=.1,end=.8)])
        request=Mock(side_effect=[bad,dict(connections=good['connections']),geometry,actions])
        parts,events=plan_custom_mechanism('Explain a battery, switch and coil with a mechanical return spring',
            [dict(narration='Hook'),dict(narration='Close the switch'),dict(narration='Current flows')],request,None,'small')
        schemas=[list(c.args[2]['properties']) for c in request.call_args_list]
        self.assertEqual(schemas,[['components','connections'],['connections'],['parts'],['actions']])
        self.assertIn('Battery:negative',request.call_args_list[1].args[0])
        allowed=request.call_args_list[1].args[2]['properties']['connections']['items']['properties']['links']['items']['enum']
        self.assertNotIn('Return spring:left',allowed)
        self.assertEqual({p.part.label for p in parts},{'Battery','Switch','Coil','Resistor','Return spring','Feed','Switched lead','Return','Load return'})
        self.assertEqual({a.part for a in events if a.effect=='current'},{'Feed','Switched lead','Return','Load return'})
        self.assertFalse(conducting_wires(parts,{'switch':False}))


    def test_bad_solenoid_inventory_compiles_without_another_model_guess(self):
        raw=dict(components=[
            component('battery','capacitor','source'),component('switch','solid','conductor'),component('coil','solid','load'),
            dict(name='iron_rod',shape='solid',motion='slide',electrical_role='conductor',function='Sliding ferromagnetic core pulled into the coil'),
            dict(name='spring',shape='solid',motion='deform',electrical_role='none',function='Stores energy to return the rod'),
            dict(name='housing',shape='solid',motion='fixed',electrical_role='none',function='Holds the mechanical parts')],
            connections=[connection('battery','switch:left','coil:left'),connection('battery','spring:right','coil:right')])
        inv=_inventory(raw,SHAPES)
        self.assertEqual({tuple(w['links']) for w in inv['connections']},{('battery:positive','switch:left'),('switch:right','coil:left'),('coil:right','battery:negative')})
        graph=inventory_graph(inv['components'],inv['connections'])
        self.assertEqual(conducting_wires(graph,{'switch':True}),{w['name'] for w in inv['connections']})
        self.assertFalse(conducting_wires(graph,{'switch':False}))
        self.assertEqual(len(inv['components']),6)

    def test_complex_bad_polarity_still_needs_explicit_repair(self):
        raw=solenoid();raw['components'].append(component('Other load','led'))
        raw['connections'][-1]['links'][-1]='Battery:positive'
        with self.assertRaises(CircuitInventoryError):_inventory(raw,SHAPES)

    def test_wire_repair_uses_streaming_and_a_compact_prediction_budget(self):
        from ai_video import _request_storyboard
        schema=_wiring_schema(_inventory(solenoid(),SHAPES))
        response=Mock();response.iter_lines.return_value=[json.dumps(dict(message=dict(content='{"connections":[]}'),done=True)).encode()]
        with patch('ai_video.requests.post',return_value=response) as post:
            self.assertEqual(_request_storyboard('Fix circuit','Instructions',schema,None,False,True,'small'),'{'+'"connections":[]}')
        body=post.call_args.kwargs['json']
        self.assertTrue(body['stream']);self.assertFalse(body['think'])
        self.assertEqual(body['options']['num_predict'],1600)
        response.close.assert_called_once()


if __name__=='__main__':unittest.main()
