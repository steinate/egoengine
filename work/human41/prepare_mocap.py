import sys,json
from pathlib import Path
ROOT=Path('/vepfs/public/pengjiaqi/interndata-human-pair');BASE=ROOT/'human41'
sys.path.insert(0,str(ROOT/'runtime41/kit/exts/omni.usd.libs'))
from pxr import Usd,UsdSkel
import numpy as np
from scipy.spatial.transform import Rotation
data=np.load(BASE/'output/worker-skeleton.npz');names=data['names'].tolist();short=[n.split('/')[-1] for n in names];parents=[names.index(n.rsplit('/',1)[0]) if '/' in n else -1 for n in names]
rest=data['rest'].transpose(0,2,1).copy();rest[:,:3,3]*=.01
def fk(local):
 world=local.copy()
 for i,p in enumerate(parents):
  if p>=0:world[i]=world[p]@local[i]
 return world
poses=[];labels=[]
asset=BASE/'assets/characters/Assets/Characters/Reallusion/Worker'
for name in ['Worker_Idle_Pose','Kitchen_CleanTable_M','Market_Sales_SortOut_M','Market_Sales_Assisting_M']:
 stage=Usd.Stage.Open(str(asset/'Motions'/(name+'.usd')));anim=UsdSkel.Animation(stage.GetPrimAtPath('/Worker/Animation'));jn=list(anim.GetJointsAttr().Get());ids=[names.index(n) for n in jn]
 for t in anim.GetRotationsAttr().GetTimeSamples()[::15]:
  local=rest.copy();qs=anim.GetRotationsAttr().Get(t);xyz=np.array(anim.GetTranslationsAttr().Get(t))*.01
  rot=Rotation.from_quat([list(q.GetImaginary())+[q.GetReal()] for q in qs]).as_matrix()
  local[ids,:3,:3]=rot;local[ids,:3,3]=xyz
  # Remove horizontal mocap root translation, preserve vertical body posture.
  g=fk(local);offset=g[short.index('Hip'),:2,3].copy();local[0,:2,3]-=offset
  poses.append(local);labels.append([name,t])
poses=np.array(poses);global_poses=np.array([fk(p) for p in poses]);world=np.diag([-1.,-1.,1.,1.]);global_poses=world@global_poses
np.savez(BASE/'output/worker-mocap-prior.npz',local=poses,global_world=global_poses,names=names,parents=parents,labels=np.array(labels,dtype=str),rest=rest)
report={'sample_count':len(poses),'sources':sorted(set(l[0] for l in labels)),'source':'Included Reallusion ActorCore character motions; empirical pose library, not VPoser or a trained grasp policy','bones':{n:global_poses[0,short.index(n),:3,3].tolist() for n in ['Head','R_Upperarm','R_Forearm','R_Hand','R_Index1','R_Index2','R_Index3','R_Thumb1','R_Thumb2','R_Thumb3']}}
target=np.array([.24,.32,1.1]);ds=np.linalg.norm(global_poses[:,short.index('R_Hand'),:3,3]-target,axis=-1);best=np.argsort(ds)[:6];report['nearest_wrist_candidates']=[{'index':int(k),'source':labels[k],'distance_m':float(ds[k]),'wrist':global_poses[k,short.index('R_Hand'),:3,3].tolist(),'elbow':global_poses[k,short.index('R_Forearm'),:3,3].tolist(),'forearm_rest_delta_rotvec':Rotation.from_matrix(rest[short.index('R_Forearm'),:3,:3].T@poses[k,short.index('R_Forearm'),:3,:3]).as_rotvec().tolist()} for k in best]
(BASE/'output/mocap-inspection.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
