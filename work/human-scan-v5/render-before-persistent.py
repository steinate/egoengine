"""Render exact official episode with a human actor in Isaac Sim 4.1."""
import sys,json,argparse,hashlib
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--frames',default='');p.add_argument('--preview',action='store_true');p.add_argument('--start',type=int,default=0);p.add_argument('--end',type=int);p.add_argument('--job',default='');p.add_argument('--view',choices=['both','ego','front'],default='both');a=p.parse_args();tag=a.view+('-'+a.job if a.job else '')
ROOT=Path('/vepfs/public/pengjiaqi/interndata-human-pair');BASE=ROOT/'human-scan-v5';OLD=ROOT/'human-natural-v4';OUT=BASE/('preview' if a.preview else 'render');OUT.mkdir(exist_ok=True)
sys.argv=[sys.argv[0],'--allow-root','--portable-root',str(ROOT/('cache41/kit-v3-'+tag)),f'--/log/file={OUT}/kit-{tag}.log','--/app/hydraEngine/waitIdle=true','--/app/updateOrder/checkForHydraRenderComplete=1000','--/app/useFabricSceneDelegate=false']
from omni.isaac.kit import SimulationApp
app=SimulationApp({'headless':True,'multi_gpu':False,'width':1280,'height':720,'renderer':'PathTracing','anti_aliasing':3})
try:
 import carb
 carb.settings.get_settings().set("/rtx/pathtracing/spp",32)
 carb.settings.get_settings().set("/rtx/pathtracing/totalSpp",64)
 carb.settings.get_settings().set("/rtx/pathtracing/optixDenoiser/enabled",True)
 import numpy as np,omni.usd
 import omni.replicator.core as rep
 from omni.isaac.core import World
 from omni.isaac.core.utils.stage import is_stage_loading
 from omni.isaac.core.prims import XFormPrim
 from pxr import Usd,UsdGeom,UsdPhysics,Gf,Vt
 from PIL import Image
 from scipy.spatial.transform import Rotation
 source=OLD/'human-animation.npz';data=np.load(source);cache=OLD/'skin-cache';manifest=json.loads((cache/'manifest.json').read_text());original=BASE/'source';meta=json.loads((original/'scene-meta.json').read_text())
 assert hashlib.sha256(source.read_bytes()).hexdigest()==manifest['source_sha256']
 assert manifest['max_usd_fk_position_error_m']<1e-5
 clean=Usd.Stage.Open(str(original/'source-scene.usdc'))
 for path in ['/Render','/Replicator','/Orchestrator',meta['robot_root']]:
  if clean.GetPrimAtPath(path):clean.RemovePrim(path)
 for prim in list(clean.Traverse()):
  if prim.GetTypeName()=='PhysicsScene':clean.RemovePrim(prim.GetPath())
  else:
   for api in [UsdPhysics.CollisionAPI,UsdPhysics.MeshCollisionAPI,UsdPhysics.RigidBodyAPI,UsdPhysics.MassAPI]:
    if prim.HasAPI(api):prim.RemoveAPI(api)
 clean.Export(str(BASE/('replay-scene-'+tag+'.usdc')));del clean
 omni.usd.get_context().open_stage(str(BASE/('replay-scene-'+tag+'.usdc')))
 while is_stage_loading():app.update()
 world=World(stage_units_in_meters=1.,physics_dt=1/30,rendering_dt=1/30);world.reset();stage=world.stage
 for prim in stage.Traverse():
  intensity=prim.GetAttribute('inputs:intensity')
  if intensity and intensity.Get() is not None:intensity.Set(float(intensity.Get())*.18)
 objects={n:XFormPrim(m['prim_path']) for n,m in meta['objects'].items()}
 root=UsdGeom.Xform.Define(stage,'/World/Human');W=data['world_transform'].copy();W[:3,:3]*=.01;root.AddTransformOp().Set(Gf.Matrix4d(W.T.tolist()))
 def look(eye,target):
  eye=np.array(eye);z=eye-np.array(target);z/=np.linalg.norm(z);x=np.cross([0,0,1],z);x/=np.linalg.norm(x);y=np.cross(z,x);T=np.eye(4);T[:3,:3]=np.stack([x,y,z],1);T[:3,3]=eye;return T
 configs={'ego':data['camera_world_usd'][0]}
 front_T=look([0.,1.75,1.35],[0.,-.50,.91]);configs['front']=front_T
 if a.view!='both':configs={a.view:configs[a.view]}
 annotators={};camops={};products=[]
 for name,T in configs.items():
  c=UsdGeom.Camera.Define(stage,'/World/'+name);camops[name]=c.AddTransformOp();camops[name].Set(Gf.Matrix4d(T.T.tolist()));c.CreateFocalLengthAttr(20. if name=='ego' else 25.5);c.CreateHorizontalApertureAttr(36.);c.CreateVerticalApertureAttr(20.25);c.CreateClippingRangeAttr(Gf.Vec2f(.045 if name=='ego' else .025,100.));rp=rep.create.render_product(str(c.GetPath()),(1280,720));an=rep.AnnotatorRegistry.get_annotator('rgb');an.attach([rp]);annotators[name]=an;products.append(rp);(OUT/name).mkdir(exist_ok=True)
 samples=[i for i in [0,137,258,433,474,780,1006,1044,1130,1331,1506] if i in data['source_frame']] if a.preview else list(range(a.start,min(a.end or len(data['source_frame']),len(data['source_frame']))));previous=None;position_errors=[];rotation_errors=[]
 if a.frames:samples=[int(v) for v in a.frames.split(",")]
 scan_hash=hashlib.sha256((BASE/'scan-animation.npz').read_bytes()).hexdigest()
 scanroot=stage.DefinePrim('/World/Scan','Xform');scanroot.GetReferences().AddReference(str(BASE/'scan-template.usdc'),'/ScannedHands')
 for count,i in enumerate(samples):
  di=int(np.where(data['source_frame']==i)[0][0])
  scan=np.load(BASE/'scan-cache'/f'{i:04d}.npz');assert str(scan['animation_sha256'])==scan_hash;assert int(scan['source_frame'])==i
  for side in ['L','R']:
   m=UsdGeom.Mesh(stage.GetPrimAtPath('/World/Scan/'+side));m.GetPointsAttr().Set(Vt.Vec3fArray.FromNumpy(scan[side+'_points']));m.GetNormalsAttr().Set(Vt.Vec3fArray.FromNumpy(scan[side+'_normals']))
  if previous is not None:
   for old in previous:stage.RemovePrim(old)
  paths={};baked=np.load(cache/f'{i:04d}.npz')
  for variant in annotators:
   path=f'/World/Human/{variant}_{i:04d}';paths[variant]=path;avatar=stage.DefinePrim(path,'Xform');avatar.GetReferences().AddReference(str(BASE/('ego-body-template.usdc' if variant=='ego' else 'visual-body-template.usdc')),'/Worker')
   for j,original_path in enumerate(manifest['mesh_paths']):
    mesh=UsdGeom.Mesh(stage.GetPrimAtPath(path+original_path[len('/Worker'):]))
    mesh.GetPointsAttr().Set(Vt.Vec3fArray.FromNumpy(baked[f'points_{j}']));mesh.GetNormalsAttr().Set(Vt.Vec3fArray.FromNumpy(baked[f'normals_{j}']));mesh.SetNormalsInterpolation('vertex')
   UsdGeom.Imageable(avatar).MakeInvisible()
  previous=list(paths.values())
  for n,obj in objects.items():
   T=data[n+'_world'][di];q=Rotation.from_matrix(T[:3,:3]).as_quat()[[3,0,1,2]];obj.set_world_pose(T[:3,3],q)
  if 'ego' in camops:camops['ego'].Set(Gf.Matrix4d(data['camera_world_usd'][di].T.tolist()))
  for name,an in annotators.items():
   for variant,path in paths.items():
    im=UsdGeom.Imageable(stage.GetPrimAtPath(path))
    if variant==name:im.MakeVisible()
    else:im.MakeInvisible()
   for _ in range(12 if count==0 else 2):rep.orchestrator.step(rt_subframes=2,pause_timeline=True,delta_time=1/30)
   rgb=np.asarray(an.get_data())[...,:3].copy();assert rgb.shape==(720,1280,3) and rgb.std()>1;Image.fromarray(rgb).save(OUT/name/f'{i:04d}.png')
  for n,obj in objects.items():
   pos,q=obj.get_world_pose();position_errors.append(float(np.linalg.norm(pos-data[n+'_world'][di,:3,3])));R=Rotation.from_quat(q[[1,2,3,0]]).as_matrix();rotation_errors.append(float(Rotation.from_matrix(R.T@data[n+'_world'][di,:3,:3]).magnitude()))
  if count%20==0 or a.preview:print('RENDERED',i,'pos_error',max(position_errors),'rot_error',max(rotation_errors),flush=True)
 result={'scan_source':'Digital Reality Lab Hand Scan Sample; actual 8K diffuse; mirrored hand; existing Worker body', 'scan_animation_sha256':scan_hash,'frames':len(samples),'fps':15,'source_frames':samples,'source_world_tracks_sha256':json.loads((OLD/'retarget-report.json').read_text())['source_sha256'],'source_animation_sha256':manifest['source_sha256'],'max_object_position_error_m':max(position_errors),'max_object_rotation_error_rad':max(rotation_errors),'max_usd_fk_position_error_m':manifest['max_usd_fk_position_error_m'],'renderer':'Isaac Sim 4.1 RTX PathTracing; DRL scan hands','camera':'Ego from posed eye bones; closer frontal full-body observer','front_camera_world_usd':front_T.tolist(),'front_focal_length_mm':25.5,'camera_K':[[1280*20/36,0,640],[0,1280*20/36,360],[0,0,1]],'physics':'Replay of verified stable-stack robot episode generated by official pipeline with task-local placement fixes; no new human dynamics simulation','scene':'Original saved official stage with robot removed and full human character substituted','light_intensity_multiplier':.18,'ego_visibility':'Own head, face and hat hidden for first person; full avatar used in observer view'}
 (OUT/('verification-'+tag+'.json')).write_text(json.dumps(result,indent=2));print('RENDER_DONE',json.dumps(result),flush=True)
except BaseException:
 import traceback;traceback.print_exc();raise
finally:app.close(wait_for_replicator=False)
