"""Audit visual mesh overlap using saved poses, without rerunning physics.

The observed left finger position is exact; right finger is omitted because the
official logger stores only one finger position. Parent object transform is
identity in this task, and object scale is taken from recorded observations.
"""
import json,pickle
from pathlib import Path
import numpy as np
import lmdb,trimesh
from scipy.spatial.transform import Rotation
from pxr import Usd,UsdGeom
root=Path('/vepfs/public/pengjiaqi/interndata-human-pair');assets=root/'assets/InternDataAssets/assets'
episode=root/'outputs41/official-single-pick/BananaBaseTask/franka/single_pick/omniobject3d-bottle/2026-11-12_09_05_07_712695'
rs=Usd.Stage.Open(str(assets/'franka/robot.usd'))
bs=Usd.Stage.Open(str(assets/'pick_and_place/pre-train-pick/assets/omniobject3d-bottle/google_scan-bottle_0011/Aligned_obj.usd'))
def mat(prim):return np.array(UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())).T
def transform(p,q):
    t=np.eye(4);t[:3,3]=p;t[:3,:3]=Rotation.from_quat(np.array(q)[[1,2,3,0]]).as_matrix();return t
def mesh(stage,path,body):
    prim=stage.GetPrimAtPath(path);g=UsdGeom.Mesh(prim);v=np.array(g.GetPointsAttr().Get());ids=np.array(g.GetFaceVertexIndicesAttr().Get());counts=np.array(g.GetFaceVertexCountsAttr().Get());faces=[];start=0
    for n in counts:
        for j in range(1,int(n)-1):faces.append([ids[start],ids[start+j],ids[start+j+1]])
        start+=int(n)
    m=trimesh.Trimesh(vertices=v,faces=faces,process=True)
    m.apply_transform(np.linalg.inv(mat(stage.GetPrimAtPath(body)))@mat(prim));return m
hand='/panda/fr3/panda_hand';finger='/panda/fr3/panda_leftfinger'
hm=mesh(rs,hand+'/geometry/panda_hand',hand);fm=mesh(rs,finger+'/geometry/panda_leftfinger',finger)
bm=mesh(bs,'/World/Aligned/Scan','/World/Aligned')
joint=rs.GetPrimAtPath(hand+'/panda_finger_joint1')
def jf(i):
    q=joint.GetAttribute('physics:localRot'+str(i)).Get();p=joint.GetAttribute('physics:localPos'+str(i)).Get()
    return transform(np.array(p),[q.GetReal(),*q.GetImaginary()])
j0,j1=jf(0),jf(1)
def finger_tf(q):
    slide=np.eye(4);slide[0,3]=q;return j0@slide@np.linalg.inv(j1)
authored_rel=np.linalg.inv(mat(rs.GetPrimAtPath(hand)))@mat(rs.GetPrimAtPath(finger))
rest_slide=np.linalg.inv(j0)@authored_rel@j1
joint_rest_error=float(np.max(np.abs(authored_rel-finger_tf(rest_slide[0,3]))))
assert joint_rest_error<1e-6,'Joint-frame reconstruction failed'
assert np.max(np.abs(mat(bs.GetPrimAtPath('/World'))-np.eye(4)))<1e-8,'Object parent is not identity'
env=lmdb.open(str(episode/'lmdb'),readonly=True,lock=False)
with env.begin() as txn:
    def get(k):return np.asarray(pickle.loads(txn.get(k.encode())))
    p=get('pick_object_left/translation');q=get('pick_object_left/orientation');scale=get('pick_object_left/scale')
    th=get('T_world_base')@get('T_base_ee_fl');width=get('states.gripper.position').reshape(-1)
rows=[]
for i in list(range(60,130,5))+[129]:
    # All queries are in the hand frame to preserve numerical precision.
    ob=bm.copy();ob.apply_scale(scale[i]);ob.apply_transform(np.linalg.inv(th[i])@transform(p[i],q[i]))
    lf=fm.copy();lf.apply_transform(finger_tf(width[i]/2))
    row={'frame':i,'left_finger_joint_m':float(width[i]/2),'object_world_position_m':p[i].tolist()}
    for name,m in [('left_finger',lf),('palm',hm)]:
        # Positive signed distance means inside a closed mesh. Both directions
        # are sampled to catch thin finger surfaces crossing the bottle.
        samples=m.vertices
        distance=trimesh.proximity.signed_distance(ob,samples)
        reverse=trimesh.proximity.signed_distance(m,ob.vertices[::max(1,len(ob.vertices)//6000)])
        row[name]={'max_sampled_depth_m':float(max(distance.max(),reverse.max(),0)),
            'finger_vertices_inside_object':int((distance>1e-5).sum()),'gripper_mesh_watertight':bool(m.is_watertight)}
    rows.append(row);print(json.dumps(row),flush=True)
out=root/'outputs41/collision-audit';out.mkdir(exist_ok=True)
report={'joint_frame_reconstruction_vs_authored_rest_max_error':joint_rest_error,'object_mesh_watertight':bool(bm.is_watertight),
        'geometry_vertices':{'bottle':len(bm.vertices),'left_finger':len(fm.vertices),'palm':len(hm.vertices)},
        'method':'sampled visual-mesh signed distances; only reliable for closed meshes; not a contact-force or cooked-collider test',
        'frames':rows}
(out/'recorded-contact.json').write_text(json.dumps(report,indent=2));print('CONTACT_AUDIT_DONE',flush=True)
