import unittest

import numpy as np

from explainer_parts import Part
from mechanism_animation import Action, Component, _electrical_shape
from mechanism_3d import Mechanism3D, Mechanism3DShot
from electrical_detail import rounded_route, swept_tube


def component(shape,label=None,points=((25,20),(75,80))):
    label=label or shape.title()
    return Component(Part(label,(label,),'detail',label),shape,'#91aabd',(50,50),points)


class ElectricalDetailTests(unittest.TestCase):
    def test_battery_is_a_marked_cell_with_electrically_connected_end_contacts(self):
        item=component('battery')
        model=Mechanism3D(((item,),()))
        roles=set(model.roles.values())
        self.assertTrue({'shell_front','shell','shell_print','positive_terminal','negative_terminal','gasket','internal'}<=roles)
        for role,port in (('positive_terminal',(50,20)),('negative_terminal',(50,80))):
            vertices=np.concatenate([row[3][:,:3] for row in model.compiled if model.roles[row[2]]==role])
            self.assertLess(np.linalg.norm(vertices-model.world(port),axis=1).min(),1e-6)

    def test_capacitor_has_a_can_and_foil_cutaway_not_just_two_flat_plates(self):
        model=Mechanism3D(((component('capacitor'),),()))
        roles=set(model.roles.values())
        self.assertTrue({'shell_front','shell_print','can_top','rubber_bung','safety_vent','lead','internal'}<=roles)
        wide=Mechanism3DShot(model,(180,320),0,'wide').at(0)[0]
        detail=Mechanism3DShot(model,(180,320),0,'detail').at(0)[0]
        wide_roles={model.roles[row[0]] for row in wide}
        detail_roles={model.roles[row[0]] for row in detail}
        self.assertNotIn('internal',wide_roles)
        self.assertIn('shell_front',wide_roles)
        self.assertIn('internal',detail_roles)
        self.assertNotIn('shell_front',detail_roles)
        self.assertNotIn('can_top',detail_roles)
        for port in ((25,50),(75,50)):
            leads=np.concatenate([row[3][:,:3] for row in model.compiled if model.roles[row[2]]=='lead'])
            self.assertLess(np.linalg.norm(leads-model.world(port),axis=1).min(),1e-6)

    def test_insulated_wire_keeps_ports_and_emits_one_set_of_current_markers(self):
        item=component('wire',points=((10,25),(10,70),(90,70)))
        events=(Action(1,'Wire','current',(1,0),0,.1),)
        model=Mechanism3D(((item,),events))
        self.assertTrue({'conductor','insulation','copper_strands','ferrule'}<=set(model.roles.values()))
        route=model.routes['Wire']
        np.testing.assert_allclose(route[0],model.world(item.points[0],.085))
        np.testing.assert_allclose(route[-1],model.world(item.points[-1],.085))
        objects=Mechanism3DShot(model,(180,320),1,duration=3.).at(1.)[0]
        self.assertEqual(sum(row[0]=='sphere' for row in objects),5)

    def test_wire_bends_are_smooth_finite_and_keep_the_terminal_positions(self):
        points=np.array(((0.,0.,0.),(0.,1.,0.),(1.,1.,0.)))
        route=rounded_route(points,.2)
        np.testing.assert_allclose(route[[0,-1]],points[[0,-1]])
        vertices=swept_tube(route,.035)
        self.assertTrue(np.isfinite(vertices).all())
        np.testing.assert_allclose(np.linalg.norm(vertices[:,3:],axis=1),1.,atol=1e-6)
        # A reverse bend must not create NaNs in its transported frame.
        self.assertTrue(np.isfinite(swept_tube(((0,0,0),(1,0,0),(0,0,0)),.03)).all())

    def test_ai_named_components_use_physical_models_while_separate_parts_are_preserved(self):
        for name,native in (('Battery','battery'),('Electrolytic capacitor','capacitor'),
                            ('Resistor','resistor'),('LED','led'),('Lamp','bulb')):
            self.assertEqual(_electrical_shape(name,'plate'),native)
        self.assertEqual(_electrical_shape('Copper wire','pipe'),'wire')
        self.assertEqual(_electrical_shape('Positive plate','plate'),'plate')
        self.assertEqual(_electrical_shape('Switch blade','contour'),'contour')
        self.assertEqual(_electrical_shape('Motor shaft','oval'),'oval')

    def test_motor_only_rotates_the_rotor_leaving_case_magnets_and_brushes_fixed(self):
        item=component('motor')
        model=Mechanism3D(((item,),(Action(1,'Motor','turn',(120,0),0,1),)))
        shot=Mechanism3DShot(model,(180,320),1,duration=3.)
        before={row[0]:row[2] for row in shot.at(0.)[0]}
        after={row[0]:row[2] for row in shot.at(2.9)[0]}
        for name,role in model.roles.items():
            if role=='rotor':
                self.assertFalse(np.allclose(before[name],after[name]))
            else:
                np.testing.assert_allclose(before[name],after[name],atol=1e-8)


if __name__=='__main__':
    unittest.main()
