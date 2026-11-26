import json
import unittest
from unittest.mock import Mock, patch

import numpy as np

from ai_video import MAX_PROMPT, OLLAMA_MODEL, _fit_runtime, _plan_mechanism, _request_storyboard, plan_video, validate_generation
from dc_circuit import CircuitShot, circuit_mechanism, circuit_state, matches_circuit
from electrical_components import electrical_meshes
from electrical_relay import RelayShot, matches_relay, relay_mechanism
from mechanism_3d import Mechanism3D, Mechanism3DShot
from mechanism_animation import Component, ELECTRICAL_SHAPES, current_level, mechanism_schema, parse_mechanism_rows


PROMPT = ('Create a simple 3D educational animation explaining how electricity flows through a circuit. '
          'Show electrons moving through a copper wire from a battery, passing through a switch and lighting a bulb. '
          'Reveal electron flow, voltage and current using glowing blue and orange particles. '
          'Show closing and opening the switch. Dark background, clear labels. Vertical 9:16, 25 seconds.')


class ElectricalStudioTests(unittest.TestCase):
    def test_long_prompt_is_preserved_and_over_limit_rejected_explicitly(self):
        prompt = PROMPT+' Explain every connection and transition clearly.'*170
        self.assertGreater(len(prompt),1200)
        self.assertEqual(validate_generation({'prompt':prompt,'max_seconds':25})['prompt'],prompt)
        self.assertEqual(validate_generation({'prompt':'a'*MAX_PROMPT})['prompt'],'a'*MAX_PROMPT)
        with self.assertRaisesRegex(ValueError,str(MAX_PROMPT)):
            validate_generation({'prompt':'a'*(MAX_PROMPT+1)})
        self.assertLessEqual(sum(_fit_runtime([375,390],25)[0]),25*30)
        self.assertEqual(validate_generation({'prompt':PROMPT,'max_seconds':90})['max_seconds'],25)

    def test_exact_circuit_prompt_does_not_depend_on_unreliable_layout_generation(self):
        with patch('ai_video._request_storyboard',side_effect=AssertionError('Unexpected AI call')):
            template,_,description,scenes = plan_video(PROMPT,None,max_seconds=25)
            parts,actions = _plan_mechanism(PROMPT,scenes)
        self.assertEqual(template.id,'dc-circuit')
        self.assertEqual(len(scenes),6)
        self.assertIn('opposite',description)
        self.assertTrue(any(part.shape=='bulb' for part in parts))
        self.assertFalse(matches_circuit(PROMPT+' Add a parallel capacitor and a relay.'))
        from narration_budget import word_count
        for maximum in (60,90,120):
            self.assertLessEqual(word_count(plan_video(PROMPT,None,max_seconds=maximum)[3]),150)

    def test_detailed_relay_prompt_has_a_reviewed_isolated_circuit_and_working_contacts(self):
        prompt = ('Explain a low-voltage DC relay with a normally open lamp contact. '
                  'Show the fixed coil, moving armature and return spring. '+
                  'Keep the control and load circuits electrically isolated. '*100)
        with patch('ai_video._request_storyboard',side_effect=AssertionError('Unexpected AI call')):
            template,_,_,scenes=plan_video(prompt,None)
            mechanism=_plan_mechanism(prompt,scenes)
        self.assertEqual(template.id,'dc-relay')
        self.assertFalse(matches_relay('Explain a solid-state relay.'))
        self.assertFalse(matches_relay('Explain a normally closed relay.'))
        model=Mechanism3D(mechanism)
        anchor=np.append(model.world((63,36)),1.)
        spring_end=np.append(model.world((63,48)),1.)
        arm_tip=np.append(model.world((66,48)),1.)
        for beat in range(6):
            for fraction in np.linspace(0,1,12):
                shot=RelayShot(model,(180,320),beat,duration=3.)
                objects=shot.at(fraction*(3-1/30))[0]
                arm=next(row[2] for row in objects if row[3]=='Steel armature')
                spring=next(row[2] for row in objects if row[3]=='Return spring')
                np.testing.assert_allclose(spring@anchor,anchor,atol=1e-7)
                np.testing.assert_allclose(spring@spring_end,arm@spring_end,atol=1e-7)
                load_events=[a for a in model.actions if a.part=='Lamp feed']
                if current_level(load_events,beat,fraction):
                    expected=model.world((34+32*np.cos(np.deg2rad(11)),48+32*np.sin(np.deg2rad(11))))
                    np.testing.assert_allclose((arm@arm_tip)[:3],expected,atol=1e-7)

    def test_current_only_runs_when_the_blade_touches_the_contact(self):
        for beat in range(6):
            for fraction in np.linspace(0,1,41):
                angle,closed = circuit_state(beat,fraction)
                if closed:
                    self.assertAlmostEqual(angle,0.,places=9)
                elif abs(angle)>1e-7:
                    self.assertFalse(closed)
        model = Mechanism3D(circuit_mechanism(6))
        for beat,time,expected in ((1,2.,False),(2,.2,False),(2,3.,True),(4,2.,True),(5,2.,False)):
            objects,_,_ = CircuitShot(model,(180,320),beat,duration=4.).at(time)
            markers = [row for row in objects if row[0]=='sphere']
            self.assertEqual(bool(markers),expected)
            if expected:
                self.assertEqual(len(markers),60)
                self.assertEqual(len({row[1] for row in markers}),2)

    def test_current_persists_between_beats_and_stops_when_told(self):
        parts,actions = circuit_mechanism(6)
        events = [event for event in actions if event.part=='Positive wire']
        self.assertEqual(current_level(events,1,1.),0)
        self.assertEqual(current_level(events,2,.49),1)
        self.assertEqual(current_level(events,3,.1),1)
        self.assertEqual(current_level(events,5,.16),0)
        model = Mechanism3D((parts,actions))
        first = Mechanism3DShot(model,(180,320),3,duration=3.,offset=10.)
        second = Mechanism3DShot(model,(180,320),4,duration=3.,offset=13.)
        a = [row[2] for row in first.at(3.)[0] if row[0]=='sphere']
        b = [row[2] for row in second.at(0.)[0] if row[0]=='sphere']
        np.testing.assert_allclose(a,b,atol=1e-7)

    def test_typed_plans_support_native_electrical_components(self):
        data = {'parts':[
            {'name':'Copper wire','shape':'wire','color':'gold','pivot':[10,50],'points':[[10,50],[90,50]]},
            {'name':'Cell','shape':'battery','color':'dark','pivot':[20,30],'points':[[15,15],[25,45]]},
            {'name':'Load','shape':'bulb','color':'white','pivot':[75,30],'points':[[65,15],[85,45]]}],
            'actions':[{'beat':beat,'part':'Copper wire','effect':'current','amount':[level,0],'start':0.,'end':.2}
                       for beat,level in ((1,1),(2,-1),(3,0))]}
        model = Mechanism3D(parse_mechanism_rows(data,4))
        self.assertGreater(len(model.compiled),3)
        self.assertEqual(mechanism_schema(4)['properties']['parts']['items']['type'],'object')
        for shape in ELECTRICAL_SHAPES:
            if shape=='wire':
                continue
            component = Component(model.parts[1].part,shape,'#91aabd',(20,30),((15,15),(25,45)))
            from mechanism_3d import _wire
            pieces = electrical_meshes(component,model.world,_wire)
            self.assertTrue(pieces,shape)
            for vertices,material,role in pieces:
                self.assertTrue(np.isfinite(vertices).all(),shape)
                np.testing.assert_allclose(np.linalg.norm(vertices[:,3:],axis=1),1.,atol=1e-5)

    def test_long_prompt_gets_more_model_context_without_truncation(self):
        prompt = 'Detailed circuit constraints. '*400
        response = Mock()
        response.iter_lines.return_value = [json.dumps({'message':{'content':'{}'},'done':True}).encode()]
        with patch('ai_video.requests.post',return_value=response) as post:
            _request_storyboard(prompt,'Plan this exact circuit.',mechanism_schema(6),None,False,True,OLLAMA_MODEL)
        body = post.call_args.kwargs['json']
        self.assertEqual(body['messages'][1]['content'],prompt)
        self.assertGreater(body['options']['num_ctx'],8192)
        self.assertLessEqual(body['options']['num_ctx'],16384)
        self.assertGreaterEqual(body['options']['num_predict'],4000)

    def test_layout_retry_receives_the_failed_draft_and_specific_timing_error(self):
        data={'parts':['Track|plate|steel|50,72|12,70 88,75',
                       'Gate|contour|blue|25,68|25,40 59,40 59,68 25,68',
                       'Handle|pipe|gold|30,48|30,48 45,48'],
              'actions':['1|Gate|move|12,0|.1,.7','2|Gate|move|-12,0|.1,.7','3|Handle|move|12,0|.1,.7']}
        invalid={**data,'actions':['1|Gate|move|12,0|0,0',*data['actions'][1:]]}
        with patch('ai_video._ollama_models',return_value={OLLAMA_MODEL}), \
             patch('ai_video._request_storyboard',side_effect=[json.dumps(invalid),json.dumps(data)]) as request:
            _plan_mechanism('Explain a sliding gate in detail.'*60,[{'narration':'The gate moves.'}]*4)
        retry=request.call_args_list[1].args
        self.assertIn('Previous draft to correct',retry[0])
        self.assertIn('1|Gate|move|12,0|0,0',retry[0])
        self.assertIn('start < end',retry[1])


if __name__=='__main__':
    unittest.main()
