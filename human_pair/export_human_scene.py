"""Recreate official seed-42 scene, then export recorded episode geometry.
No planning changes; output is a visual replay source, not another success claim.
"""
import sys,json
from pathlib import Path
import numpy as np
ROOT=Path('/vepfs/public/pengjiaqi/interndata-human-pair')
OUT=ROOT/'outputs41/human-ego';OUT.mkdir(parents=True,exist_ok=True)
sys.argv=[sys.argv[0],'--allow-root','--portable-root',str(ROOT/'cache41/kit'),f'--/log/file={OUT}/scene-kit.log']
from nimbus.utils.utils import init_env
from nimbus.utils.flags import set_random_seed
init_env();set_random_seed(42)
from omni.isaac.kit import SimulationApp
app=SimulationApp({'headless':True,'multi_gpu':False,'anti_aliasing':0})
try:
 from omni.isaac.core import World
 from pxr import Usd,UsdGeom,Gf
 from scipy.spatial.transform import Rotation
 from workflows import import_extensions
 import_extensions('SimBoxDualWorkFlow')
 from workflows.simbox_dual_workflow import SimBoxDualWorkFlow
 world=World(stage_units_in_meters=1.,physics_dt=1/30,rendering_dt=1/30)
 wf=SimBoxDualWorkFlow(world,'workflows/simbox/core/configs/tasks/basic/split_aloha/stack_cubes_lift/lr.yaml',random_seed=42)
 wf.init_task(0,False);wf.randomization()
 d=np.load(ROOT/'outputs41/official-dual-grasp-evidence/object-and-robot-tracks.npz')
 r=wf.task.robots['split_aloha'];base=d['T_world_base'][0]
 r.set_local_pose(base[:3,3],Rotation.from_matrix(base[:3,:3]).as_quat()[[3,0,1,2]])
 world.render()
 stage=world.stage
 def mat(path):return np.array(UsdGeom.Xformable(stage.GetPrimAtPath(path)).ComputeLocalToWorldTransform(Usd.TimeCode.Default())).T
 data={};meta={'source':'official-dual-grasp seed 42','objects':{},'robot_root':r.prim_path}
 for side,armbase,key in [('left',r.fl_base_path,'T_base_ee_fl'),('right',r.fr_base_path,'T_base_ee_fr')]:
  B=mat(armbase);data[side+'_ee_world']=B@d[key];meta[side+'_base_world']=B.tolist()
 for name,o in wf.task.objects.items():
  if name+'__translation_local_m' not in d:continue
  path=o.prim_path
  o.set_local_pose(d[name+'__translation_local_m'][0],d[name+'__orientation_wxyz'][0]);o.set_local_scale(d[name+'__scale'][0])
  parent=mat(str(stage.GetPrimAtPath(path).GetParent().GetPath()))
  local=np.tile(np.eye(4),(len(d['video_frame_index']),1,1));local[:,:3,:3]=Rotation.from_quat(d[name+'__orientation_wxyz'][:,[1,2,3,0]]).as_matrix();local[:,:3,3]=d[name+'__translation_local_m']
  data[name+'_world']=parent@local
  vertices=[];faces=[]
  rootinv=np.linalg.inv(data[name+'_world'][0])
  for prim in Usd.PrimRange(stage.GetPrimAtPath(path)):
   if prim.IsA(UsdGeom.Mesh):
    mesh=UsdGeom.Mesh(prim);v=np.array(mesh.GetPointsAttr().Get());T=rootinv@mat(str(prim.GetPath()));v=v@T[:3,:3].T+T[:3,3]
    counts=np.array(mesh.GetFaceVertexCountsAttr().Get());idx=np.array(mesh.GetFaceVertexIndicesAttr().Get());start=0;off=sum(len(a) for a in vertices)
    for count in counts:
     f=idx[start:start+count]+off
     for k in range(1,count-1):faces.append([f[0],f[k],f[k+1]])
     start+=count
    vertices.append(v)
  data[name+'_mesh_vertices']=np.concatenate(vertices);data[name+'_mesh_faces']=np.array(faces)
  meta['objects'][name]={'prim_path':path,'parent_world':parent.tolist(),'mesh_bounds_m':[data[name+'_mesh_vertices'].min(0).tolist(),data[name+'_mesh_vertices'].max(0).tolist()]}
  print('OBJECT',name,meta['objects'][name],flush=True)
 world.render()
 stage.Export(str(OUT/'source-scene.usdc'))
 np.savez_compressed(OUT/'world-tracks.npz',**data)
 (OUT/'scene-meta.json').write_text(json.dumps(meta,indent=2))
 print('SCENE_EXPORTED',flush=True)
finally:app.close()
