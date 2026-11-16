"""Isaac Sim 4.1 visual replay; object poses are imposed, no new dynamics."""
import sys,argparse,json
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--preview',action='store_true');p.add_argument('--width',type=int,default=960);p.add_argument('--height',type=int,default=540);a=p.parse_args()
ROOT=Path('/vepfs/public/pengjiaqi/interndata-human-pair');SOURCE=ROOT/'outputs41/human-ego';OUT=ROOT/'gaussian-ego/output';OUT.mkdir(exist_ok=True)
sys.argv=[sys.argv[0],'--allow-root','--portable-root',str(ROOT/'cache41/kit'),f'--/log/file={OUT}/render-kit.log']
sys.argv+=['--/app/hydraEngine/waitIdle=true','--/app/updateOrder/checkForHydraRenderComplete=1000','--/app/useFabricSceneDelegate=false']
from omni.isaac.kit import SimulationApp
app=SimulationApp({'headless':True,'multi_gpu':False,'width':a.width,'height':a.height,'anti_aliasing':3})
try:
 import omni.usd,carb
 from omni.isaac.core import World
 from omni.isaac.core.utils.stage import is_stage_loading
 from omni.isaac.core.prims import XFormPrim
 from pxr import UsdGeom,UsdShade,Sdf,Gf,Vt,Usd,UsdPhysics
 import omni.replicator.core as rep
 rep.orchestrator.set_capture_on_play(True)
 from scipy.spatial.transform import Rotation
 import imageio.v2 as imageio
 meta=json.loads((SOURCE/'scene-meta.json').read_text());human=dict(np.load(SOURCE/'human-animation.npz'));track=dict(np.load(SOURCE/'world-tracks.npz'))
 # A saved live stage contains stale synthetic-data graphs. Rebuild these for
 # the new ego camera instead of loading the old camera render products.
 clean=Usd.Stage.Open(str(SOURCE/'source-scene.usdc'))
 for path in ['/Render','/Replicator','/Orchestrator']:
  if clean.GetPrimAtPath(path):clean.RemovePrim(path)
 clean.RemovePrim(meta['robot_root'])
 for prim in list(clean.Traverse()):
  if prim.GetTypeName()=='PhysicsScene':clean.RemovePrim(prim.GetPath())
  elif prim.HasAPI(UsdPhysics.RigidBodyAPI):UsdPhysics.RigidBodyAPI(prim).GetRigidBodyEnabledAttr().Set(False)
 clean.Export(str(OUT/'replay-scene.usdc'));del clean
 omni.usd.get_context().open_stage(str(OUT/'replay-scene.usdc'))
 while is_stage_loading():app.update()
 world=World(stage_units_in_meters=1.,physics_dt=1/30,rendering_dt=1/30);world.reset();stage=world.stage
 for prim in stage.Traverse():
  intensity=prim.GetAttribute('inputs:intensity')
  if intensity and intensity.Get() is not None:intensity.Set(float(intensity.Get())*.18)
 # Cameras attached to the hidden robot are no longer rendered.
 objs={n:XFormPrim(m['prim_path']) for n,m in meta['objects'].items()}
 root='/World/HumanReference';UsdGeom.Xform.Define(stage,root)
 def material(name,color,roughness):
  m=UsdShade.Material.Define(stage,root+'/'+name);s=UsdShade.Shader.Define(stage,root+'/'+name+'/Shader');s.CreateIdAttr('UsdPreviewSurface')
  s.CreateInput('diffuseColor',Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color));s.CreateInput('roughness',Sdf.ValueTypeNames.Float).Set(roughness)
  s.CreateInput('specularColor',Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(.23,.20,.19));s.CreateInput('useSpecularWorkflow',Sdf.ValueTypeNames.Int).Set(1)
  m.CreateSurfaceOutput().ConnectToSource(s.ConnectableAPI(),'surface');return m
 skin=material('Skin',(.48,.265,.17),.47)
 nailmat=material('Nails',(.60,.39,.32),.30)
 cloth=material('Sleeves',(.025,.045,.075),.88)
 def mesh(name,faces,mat,points,subdiv='catmullClark'):
  m=UsdGeom.Mesh.Define(stage,root+'/'+name);m.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(np.asarray(points,dtype=np.float32)));m.CreateFaceVertexCountsAttr([len(faces[0])]*len(faces));m.CreateFaceVertexIndicesAttr(np.array(faces).ravel().tolist());m.CreateSubdivisionSchemeAttr(subdiv);m.CreateDoubleSidedAttr(True);UsdShade.MaterialBindingAPI.Apply(m.GetPrim()).Bind(mat);return m
 nring=36;nseg=24
 armfaces=[]
 for j in range(nring-1):
  for k in range(nseg):armfaces.append([j*nseg+k,j*nseg+(k+1)%nseg,(j+1)*nseg+(k+1)%nseg,(j+1)*nseg+k])
 def arm_mesh(points,H):
  shoulder,elbow,wrist=points.copy();wrist=wrist-H[:3,1]*.004
  # Smooth two-bone limb with an anatomically tapered forearm and upper arm.
  t=np.linspace(0,1,nring);centers=[];radii=[]
  for u in t:
   if u<.5:
    v=u*2;centers.append(wrist*(1-v)+elbow*v);radii.append(.027+.018*np.sin(v*np.pi*.68)+.0015*np.sin(13*v))
   else:
    v=(u-.5)*2;centers.append(elbow*(1-v)+shoulder*v);radii.append(.043+.018*np.sin(v*np.pi*.55)+.0015*np.sin(11*v))
  centers=np.array(centers);verts=[]
  for j,(c,r) in enumerate(zip(centers,radii)):
   axis=centers[min(j+1,nring-1)]-centers[max(j-1,0)];axis/=np.linalg.norm(axis)
   xx=H[:3,0]-axis*np.dot(H[:3,0],axis);xx/=np.linalg.norm(xx);yy=np.cross(axis,xx)
   for theta in np.linspace(0,2*np.pi,nseg,endpoint=False):verts.append(c+r*(np.cos(theta)*xx+.78*np.sin(theta)*yy))
  return np.array(verts,dtype=np.float32)

 motion=dict(np.load(OUT/'motion.npz'))
 eye=np.array([-.18,-.58,1.23]);target=np.array([.28,-.06,.88]);z=eye-target;z/=np.linalg.norm(z);x=np.cross([0.,0.,1.],z);x/=np.linalg.norm(x);y=np.cross(z,x)
 cam=UsdGeom.Camera.Define(stage,'/World/GaussianEgoCamera')
 camera_T=np.eye(4);camera_T[:3,:3]=np.stack([x,y,z],axis=1);camera_T[:3,3]=eye
 UsdGeom.Xformable(cam.GetPrim()).AddTransformOp().Set(Gf.Matrix4d(camera_T.T.tolist()))
 cam.GetFocalLengthAttr().Set(20.);cam.GetHorizontalApertureAttr().Set(20.955);cam.GetVerticalApertureAttr().Set(20.955*a.height/a.width);cam.GetClippingRangeAttr().Set(Gf.Vec2f(.01,100.))
 product=rep.create.render_product(str(cam.GetPath()),(a.width,a.height))
 rgb=rep.AnnotatorRegistry.get_annotator('rgb');rgb.attach([product])
 depth=rep.AnnotatorRegistry.get_annotator('distance_to_image_plane');depth.attach([product])
 cv=camera_T@np.diag([1.,-1.,-1.,1.]);f=20./20.955*a.width
 (OUT/'camera.json').write_text(json.dumps({'width':a.width,'height':a.height,'K':[[f,0,a.width/2],[0,f,a.height/2],[0,0,1]],'T_world_camera_opencv':cv.tolist()},indent=2))
 errors=[];last=[None]
 def frame(k):
  i=int(motion['source_frames'][k])
  for n,o in objs.items():
   T=track[n+'_world'][i];q=Rotation.from_matrix(T[:3,:3]).as_quat()[[3,0,1,2]];o.set_world_pose(T[:3,3],q)
  if last[0]!=k:
   if last[0] is not None:stage.RemovePrim(root+f'/sample_{last[0]}')
   group=f'sample_{k}';UsdGeom.Xform.Define(stage,root+'/'+group)
   H=human['right_wrist_T'][i].copy();arm=human['right_arm'][i].copy()
   wrist=motion['joints'][k,0];arm[-1]=wrist;H[:3,3]=wrist
   mesh(group+'/sleeve',armfaces,cloth,arm_mesh(arm,H))
   last[0]=k
  rep.orchestrator.step(rt_subframes=4,pause_timeline=True,delta_time=1/30)
  for n,o in objs.items():errors.append(float(np.linalg.norm(o.get_world_pose()[0]-track[n+'_world'][i,:3,3])))
 for _ in range(10):frame(0)
 ids=[0,30,60,90] if a.preview else range(len(motion['source_frames']))
 folder=OUT/'scene';folder.mkdir(exist_ok=True)
 for k in ids:
  frame(k);frame(k)
  color=rgb.get_data()[:,:,:3];z=depth.get_data()
  assert color.shape==(a.height,a.width,3) and z.shape==(a.height,a.width)
  imageio.imwrite(folder/f'{k:04d}.png',color);np.save(folder/f'{k:04d}-depth.npy',z)
  if k%15==0:print('BACKGROUND_FRAME',k,flush=True)
 (OUT/'scene-check.json').write_text(json.dumps({'frames':len(ids),'max_object_position_error_m':max(errors),'official_source_start':420,'official_source_end':510,'render':'Isaac Sim 4.1 RTX; no robot or proxy hand primary surface'},indent=2))
 print('BACKGROUND_DONE',flush=True)
except BaseException:
 import traceback
 traceback.print_exc();raise
finally:app.close(wait_for_replicator=False)
