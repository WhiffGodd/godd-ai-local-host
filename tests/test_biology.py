import unittest
from unittest.mock import patch

import numpy as np

from ai_video import _plan_mechanism, _validate_plan, plan_video
from biological_components import BIOLOGICAL_SHAPES, biological_mesh, biological_parts
from biology_explainers import BIOLOGY_REFERENCES, biology_mechanism, biology_storyboard, biology_topic
from biology_shots import BIOLOGY_SHOTS, MedicineShot, PeristalsisShot, GasExchangeShot
from explainer_parts import Part
from explainer_templates import TEMPLATES, matching_subjects
from mechanism_animation import Action, Component, biological_level, mechanism_schema
from mechanism_3d import Mechanism3D
from narration_budget import word_count
from cinematic_render import CinematicRenderer, _look_at, _perspective


class BiologyTests(unittest.TestCase):
    def test_reviewed_biology_topics_have_scripts_and_working_layouts_without_ai_requests(self):
        for topic,prompt in (('oral-medicine','Show how a pill enters the body, dissolves and does its job.'),
                             ('swallowing-peristalsis','Explain swallowing and esophageal peristalsis.'),
                             ('alveolar-gas-exchange','Explain gas exchange in the lungs and alveoli.')):
            with self.subTest(topic=topic),patch('ai_video._request_storyboard',side_effect=AssertionError('Unexpected model call')):
                self.assertEqual(matching_subjects(prompt),[TEMPLATES[topic]])
                template,_,_,scenes=plan_video(prompt,None)
                mechanism=_plan_mechanism(prompt,scenes)
                self.assertEqual(template.id,topic)
                self.assertTrue(3<=len(mechanism[0])<=24)
                self.assertGreater(len(Mechanism3D(mechanism).compiled),len(mechanism[0]))

    def test_generic_medicine_story_does_not_override_named_drugs_or_modified_release_products(self):
        for prompt in ('Explain an enteric-coated capsule.','How does ibuprofen work?',
                       'Show an extended-release tablet journey.','How a tablet press manufactures pills.',
                       'Explain sublingual tablets.','Explain topical medicine.'):
            self.assertIsNone(biology_topic(prompt),prompt)
        self.assertIsNone(biology_topic('Explain peristalsis in the colon.'))

    def test_capsule_request_uses_a_capsule_model_and_matching_script(self):
        prompt='Explain the journey of a swallowed immediate-release capsule.'
        with patch('ai_video._request_storyboard',side_effect=AssertionError('Unexpected model call')):
            _,title,_,scenes=plan_video(prompt,None,max_seconds=25)
            components,_=_plan_mechanism(prompt,scenes)
        self.assertIn('Capsule',title)
        self.assertEqual(next(c.shape for c in components if c.part.label=='Tablet'),'capsule')
        self.assertFalse(any('tablet' in scene['narration'].lower() for scene in scenes))

    def test_scripts_cover_the_whole_process_and_fit_both_duration_budgets(self):
        for topic in BIOLOGY_REFERENCES:
            for maximum,budget in ((25,72),(60,150),(90,250),(120,340)):
                board=biology_storyboard(topic,maximum)
                title,description,scenes=_validate_plan(board,'mechanism',8 if maximum>60 else 6)
                self.assertLessEqual(word_count(scenes),budget,(topic,maximum))
                self.assertIn(BIOLOGY_REFERENCES[topic][1],description)
        medicine=biology_storyboard('oral-medicine')
        narrations=[s['narration'].lower() for s in medicine['scenes']]
        self.assertIn('esophagus',narrations[0])
        self.assertIn('dissolve',narrations[1])
        self.assertIn('lining',narrations[2])
        self.assertIn('portal blood',narrations[3])
        self.assertIn('other medicines work differently',narrations[4])
        self.assertIn('kidneys',narrations[5])

    def test_solid_pill_disappears_before_absorption_and_never_enters_blood(self):
        model=Mechanism3D(biology_mechanism('oral-medicine',7))
        for beat in (3,4,5,6):
            objects=MedicineShot(model,(180,320),beat,duration=3.,offset=beat*3).at(1.)[0]
            self.assertFalse(any(row[3]=='Tablet' for row in objects))
            self.assertTrue(any(row[0]=='bio-marker' for row in objects))
        events=[a for a in model.actions if a.part=='Tablet']
        self.assertEqual(biological_level(events,'dissolve',1,1),0.)
        self.assertAlmostEqual(biological_level(events,'dissolve',2,1),1.)
        self.assertAlmostEqual(biological_level(events,'dissolve',3,0),1.)

    def test_swallowing_path_and_stomach_entry_remain_continuous_between_stages(self):
        model=Mechanism3D(biology_mechanism('oral-medicine',7))
        for before,after in ((0,1),(1,2)):
            a=MedicineShot(model,(180,320),before,duration=3.).at(3.)[0]
            b=MedicineShot(model,(180,320),after,duration=3.).at(0.)[0]
            pose_a=next(row[2] for row in a if row[3]=='Tablet')
            pose_b=next(row[2] for row in b if row[3]=='Tablet')
            np.testing.assert_allclose(pose_a,pose_b,atol=1e-7)

    def test_peristaltic_contraction_follows_behind_the_moving_bolus(self):
        model=Mechanism3D(biology_mechanism('swallowing-peristalsis',6))
        shot=PeristalsisShot(model,(180,320),3,duration=3.)
        previous_y=None
        for time in (.2,1.2,2.8):
            objects=shot.at(time)[0]
            rings=[(int(model.roles[row[0]].split(':')[1]),row[2]) for row in objects
                   if model.roles.get(row[0],'').startswith('band:')]
            tightest=min(rings,key=lambda pair:pair[1][0,0])
            y=13+74*tightest[0]/26
            self.assertLess(y,shot.bolus[1])
            self.assertAlmostEqual(y,shot.bolus[1]-8,delta=3.)
            if previous_y is not None:self.assertGreater(shot.bolus[1],previous_y)
            previous_y=shot.bolus[1]

    def test_alveoli_show_blood_cells_and_both_gases_moving(self):
        model=Mechanism3D(biology_mechanism('alveolar-gas-exchange',6))
        shot=GasExchangeShot(model,(180,320),3,duration=3.,offset=9)
        first=shot.at(.2)[0];last=shot.at(1.2)[0]
        self.assertTrue(any(row[0]=='bio-rbc' for row in first))
        colors={row[1][:3] for row in first if row[0]=='bio-marker'}
        self.assertIn((.19,.84,.97),colors)
        self.assertIn((1.,.62,.16),colors)
        a=[row[2] for row in first if row[0]=='bio-rbc']
        b=[row[2] for row in last if row[0]=='bio-rbc']
        self.assertFalse(np.allclose(a,b))

    def test_swallowing_closeup_keeps_the_bolus_above_the_caption_area(self):
        model=Mechanism3D(biology_mechanism('swallowing-peristalsis',6))
        for beat in (2,3,4,5):
            shot=PeristalsisShot(model,(180,320),beat,duration=3.)
            shot.at(2.8)
            eye,focus=shot.camera
            point=_perspective(180/320,.78)@_look_at(eye,focus)@np.append(model.world(shot.bolus),1.)
            normalized_y=(1-point[1]/point[3])/2
            self.assertLess(normalized_y,.64)
            self.assertGreater(normalized_y,.25)

    def test_red_blood_cell_has_a_biconcave_profile(self):
        vertices=biological_mesh('bio-rbc')[:,:3]
        radial=np.linalg.norm(vertices[:,:2],axis=1)
        center=np.abs(vertices[radial<.05,2]).max()
        rim=np.abs(vertices[(radial>.55)&(radial<.9),2]).max()
        self.assertGreater(rim,center*1.2)

    def test_labels_use_the_blended_camera_during_anatomy_closeups(self):
        model=Mechanism3D(biology_mechanism('oral-medicine',7))
        shot=MedicineShot(model,(180,320),3,duration=3.)
        shot.camera_from=(np.array((0.,0.,12.)),np.array((0.,0.,0.)))
        with CinematicRenderer((180,320)) as renderer:
            model.upload(renderer)
            renderer.frame(shot,.2)
            np.testing.assert_allclose(shot.camera[0],renderer.last_camera[0])
            np.testing.assert_allclose(shot.camera[1],renderer.last_camera[1])

    def test_all_anatomy_primitives_have_finite_solid_geometry_and_unit_normals(self):
        model=Mechanism3D(biology_mechanism('oral-medicine',7))
        for shape in BIOLOGICAL_SHAPES:
            with self.subTest(shape=shape):
                component=Component(Part(shape,(shape,),'detail',shape),shape,'#bf7970',(50,50),((20,20),(80,80)))
                pieces=biological_parts(component,model.world)
                self.assertTrue(pieces)
                for vertices,material,role in pieces:
                    self.assertTrue(np.isfinite(vertices).all(),(shape,role))
                    self.assertGreater(np.ptp(vertices[:,2]),0.,(shape,role))
                    np.testing.assert_allclose(np.linalg.norm(vertices[:,3:],axis=1),1.,atol=1e-5)
        schema=mechanism_schema(7)
        self.assertTrue(set(BIOLOGICAL_SHAPES)<=set(schema['properties']['parts']['items']['properties']['shape']['enum']))


if __name__=='__main__':
    unittest.main()
