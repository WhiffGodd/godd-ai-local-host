import unittest

import numpy as np

from mechanism_animation import parse_mechanism_rows, _transform
from mechanism_3d import Mechanism3D, Mechanism3DShot, extrude_profile


def gate_model():
    return parse_mechanism_rows({
        "parts":["Track|plate|steel|50,72|12,70 88,75",
                 "Gate|contour|blue|25,68|25,40 59,40 59,68 25,68",
                 "Handle|pipe|gold|30,48|30,48 45,48"],
        "actions":["1|Gate|move|12,0|.1,.7","2|Gate|move|-12,0|.1,.7",
                   "3|Handle|move|12,0|.1,.7"]},4)


class Mechanism3DTests(unittest.TestCase):
    def test_concave_part_has_real_depth_closed_sides_and_correct_face_area(self):
        profile = [(0.,0.),(3.,0.),(3.,1.),(1.,1.),(1.,3.),(0.,3.)]
        vertices = extrude_profile(profile,.20)
        self.assertAlmostEqual(float(np.ptp(vertices[:,2])),.20,places=6)
        normals = vertices[:,3:]
        np.testing.assert_allclose(np.linalg.norm(normals,axis=1),1.,atol=1e-6)
        triangles = vertices.reshape(-1,3,6)
        front = triangles[np.all(triangles[:,:,5]>.99,axis=1),:,:2]
        edges1,edges2 = front[:,1]-front[:,0],front[:,2]-front[:,0]
        area = np.sum(np.abs(edges1[:,0]*edges2[:,1]-edges1[:,1]*edges2[:,0]))/2
        self.assertAlmostEqual(float(area),5.*.982**2,places=5)
        self.assertTrue(np.any(np.abs(normals[:,2])<.01))

    def test_3d_parts_keep_the_planned_motion_and_persist_across_beats(self):
        mechanism = gate_model()
        model = Mechanism3D(mechanism)
        first = Mechanism3DShot(model,(180,320),1,duration=2.)
        next_shot = Mechanism3DShot(model,(180,320),2,duration=2.)
        before = next(row[2] for row in first.at(0.)[0] if row[3]=="Gate")
        after = next(row[2] for row in first.at(1.99)[0] if row[3]=="Gate")
        following = next(row[2] for row in next_shot.at(0.)[0] if row[3]=="Gate")
        self.assertAlmostEqual(after[0,3]-before[0,3],12*model.unit)
        np.testing.assert_allclose(after,following,atol=1e-8)
        component,events,_,_,_,z = model.compiled[1]
        target = _transform(component,events,1,1.)[0][0]
        point = np.append(model.world(component.points[0],z),1.)
        np.testing.assert_allclose((after@point)[:3],model.world(target,z),atol=1e-7)

    def test_invalid_flat_outline_is_rejected_instead_of_rendering_a_fake_part(self):
        with self.assertRaisesRegex(ValueError,"no usable area"):
            extrude_profile([(0,0),(1,0),(2,0)])


if __name__=="__main__":
    unittest.main()
