import unittest
import numpy as np
from .geometry import two_bone_ik,locked_grasp,center_mano_vertices

class GeometryTests(unittest.TestCase):
    def test_lengths_and_reach(self):
        s=np.array([0.,0.,0.]);w=np.array([.4,0.,0.])
        e=two_bone_ik(s,w,.3,.25,[0,1,0])
        self.assertAlmostEqual(np.linalg.norm(e-s),.3)
        self.assertAlmostEqual(np.linalg.norm(w-e),.25)
        self.assertGreater(e[1],0)
        with self.assertRaises(ValueError):two_bone_ik(s,[1,0,0],.3,.25,[0,1,0])
    def test_grasp_relative_pose(self):
        obj=np.tile(np.eye(4),(3,1,1));obj[:,0,3]=[0,1,2]
        rel=np.eye(4);rel[2,3]=.1
        result=locked_grasp(obj,rel)
        np.testing.assert_allclose(np.linalg.inv(obj)@result,np.broadcast_to(rel,(3,4,4)))
    def test_actual_mano_wrist_is_origin(self):
        v=np.array([[[1.,2,3],[2,2,3]]]);j=np.array([[[1.,2,3]]])
        T=np.eye(4)[None];T[0,:3,3]=[.2,.3,.4]
        out=center_mano_vertices(v,j,T)
        np.testing.assert_allclose(out[0,0],[.2,.3,.4])
        np.testing.assert_allclose(out[0,1],[1.2,.3,.4])

if __name__=='__main__':unittest.main()
