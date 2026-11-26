import json
import unittest
from unittest.mock import Mock, patch

import numpy as np
import requests

from ai_video import FPS, OLLAMA_MODEL, _fit_runtime, _plan_mechanism, _request_storyboard, plan_video, validate_generation
from explainer_templates import TEMPLATES, matching_subjects
from mechanism_animation import _outline, _transform, mechanism_schema
from mechanism_3d import Mechanism3D
from sliding_latch import latch_mechanism


PROMPT = ('Explain a spring-loaded sliding latch in one fixed side cutaway. Use five parts: '
          'fixed housing, sliding bolt, return spring, pull handle attached to the bolt, and fixed strike block. '
          'Show extended, partly retracted, fully retracted, partly returned, and fully extended.')


class LatchPlanningTests(unittest.TestCase):
    def test_exact_topic_has_a_reviewed_storyboard_and_layout_without_model_requests(self):
        self.assertEqual(matching_subjects(PROMPT),[TEMPLATES['spring-loaded-latch']])
        with patch('ai_video._request_storyboard',side_effect=AssertionError('Should not call AI')):
            template,_,_,scenes = plan_video(PROMPT,None,max_seconds=120)
            mechanism = _plan_mechanism(PROMPT,scenes)
        self.assertEqual(template,TEMPLATES['spring-loaded-latch'])
        self.assertEqual(len(scenes),6)
        self.assertEqual(len(Mechanism3D(mechanism).compiled),5)

    def test_spring_endpoint_and_handle_follow_the_bolt_during_the_entire_cycle(self):
        components,actions = latch_mechanism(6)
        parts = {component.part.label:component for component in components}
        events = lambda name:tuple(action for action in actions if action.part==name)
        for beat in range(6):
            for fraction in np.linspace(0,1,9):
                bolt,_,_,_ = _transform(parts['Sliding bolt'],events('Sliding bolt'),beat,fraction)
                spring,_,_,_ = _transform(parts['Return spring'],events('Return spring'),beat,fraction)
                handle,_,_,_ = _transform(parts['Pull handle'],events('Pull handle'),beat,fraction)
                self.assertAlmostEqual(bolt[0][0],spring[-1][0],places=7)
                self.assertAlmostEqual(handle[0][0]-bolt[0][0],4.,places=7)
        for name in ('Sliding bolt','Pull handle','Return spring'):
            first = _transform(parts[name],events(name),0,0.)[0]
            last = _transform(parts[name],events(name),5,1.)[0]
            np.testing.assert_allclose(first,last,atol=1e-8)

    def test_two_minute_cap_preserves_the_existing_duration_options(self):
        for maximum in (60,90,120):
            self.assertEqual(validate_generation({'prompt':PROMPT,'max_seconds':maximum})['max_seconds'],maximum)
        frames,tempo = _fit_runtime([4*FPS,122*FPS],120)
        self.assertEqual(sum(frames),120*FPS)
        self.assertAlmostEqual(tempo,126/120)
        self.assertEqual(_fit_runtime([72*FPS],120),([72*FPS],1.))
        with self.assertRaises(ValueError):
            validate_generation({'prompt':PROMPT,'max_seconds':121})

    def test_streamed_layout_is_assembled_and_connection_is_closed(self):
        response = Mock()
        response.iter_lines.return_value = [
            json.dumps({'message':{'content':'{"parts":[],'},'done':False}).encode(),
            json.dumps({'message':{'content':'"actions":[]}'},'done':True}).encode(),
        ]
        with patch('ai_video.requests.post',return_value=response) as post:
            result = _request_storyboard('Device','Instructions',mechanism_schema(6),None,True,True,OLLAMA_MODEL)
        self.assertEqual(json.loads(result),{'parts':[],'actions':[]})
        settings = post.call_args.kwargs
        self.assertTrue(settings['json']['stream'])
        self.assertGreaterEqual(settings['json']['options']['num_ctx'],8192)
        response.close.assert_called_once()

    def test_unfinished_layout_stream_is_not_accepted_as_a_complete_plan(self):
        response = Mock()
        response.iter_lines.return_value = [json.dumps({'message':{'content':'{"parts":['},'done':False}).encode()]
        with patch('ai_video.requests.post',return_value=response):
            with self.assertRaises(requests.ConnectionError):
                _request_storyboard('Device','Instructions',mechanism_schema(6),None,False,True,OLLAMA_MODEL)
        response.close.assert_called_once()

    def test_planning_deadline_closes_the_stream(self):
        response = Mock()
        response.iter_lines.return_value = [json.dumps({'message':{'content':'partial'},'done':False}).encode()]
        with patch('ai_video.requests.post',return_value=response), \
             patch('ai_video.time.monotonic',side_effect=[0.,181.]):
            with self.assertRaises(requests.ReadTimeout):
                _request_storyboard('Device','Instructions',mechanism_schema(6),None,False,True,OLLAMA_MODEL)
        response.close.assert_called_once()

    def test_output_budget_exhaustion_triggers_replanning(self):
        response = Mock()
        response.iter_lines.return_value = [json.dumps({'message':{'content':'{}'},'done':True,'done_reason':'length'}).encode()]
        with patch('ai_video.requests.post',return_value=response):
            with self.assertRaisesRegex(ValueError,'response budget'):
                _request_storyboard('Device','Instructions',mechanism_schema(6),None,False,True,OLLAMA_MODEL)
        response.close.assert_called_once()

    def test_network_failure_gets_an_alternative_model_attempt(self):
        rows = {'parts':['Track|plate|steel|50,72|12,70 88,75',
                         'Gate|contour|blue|25,68|25,40 59,40 59,68 25,68',
                         'Handle|pipe|gold|30,48|30,48 45,48'],
                'actions':['1|Gate|move|12,0|.1,.7','2|Gate|move|-12,0|.1,.7','3|Handle|move|12,0|.1,.7']}
        with patch('ai_video._ollama_models',return_value={OLLAMA_MODEL,'qwen3.5:9b'}), \
             patch('ai_video._request_storyboard',side_effect=[requests.ReadTimeout(),json.dumps(rows)]) as planner:
            mechanism = _plan_mechanism('Explain a sliding gate.',[{'narration':'The gate moves.'}]*4)
        self.assertEqual(len(mechanism[0]),3)
        self.assertEqual([call.args[-1] for call in planner.call_args_list],[OLLAMA_MODEL,'qwen3.5:9b'])


if __name__=='__main__':
    unittest.main()
