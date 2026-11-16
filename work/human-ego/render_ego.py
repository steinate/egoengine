"""Isaac Sim 4.1 visual replay; object poses are imposed, no new dynamics."""
import sys,argparse,json
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser();p.add_argument('--preview',action='store_true');p.add_argument('--width',type=int,default=1280);p.add_argument('--height',type=int,default=720);a=p.parse_args()
ROOT=Path('/vepfs/public/pengjiaqi/interndata-human-pair');OUT=ROOT/'outputs41/human-ego'
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
 meta=json.loads((OUT/'scene-meta.json').read_text());human=dict(np.load(OUT/'human-animation.npz'));track=dict(np.load(OUT/'world-tracks.npz'))
 # A saved live stage contains stale synthetic-data graphs. Rebuild these for
 # the new ego camera instead of loading the old camera render products.
 clean=Usd.Stage.Open(str(OUT/'source-scene.usdc'))
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
 eye=np.array([0.,-.68,1.38]);target=np.array([0.,-.14,.79]);z=eye-target;z/=np.linalg.norm(z);x=np.cross([0.,0.,1.],z);x/=np.linalg.norm(x);y=np.cross(z,x)
 cam=UsdGeom.Camera.Define(stage,'/World/HumanEgoCamera')
 camera_T=np.eye(4);camera_T[:3,:3]=np.stack([x,y,z],axis=1);camera_T[:3,3]=eye
 UsdGeom.Xformable(cam.GetPrim()).AddTransformOp().Set(Gf.Matrix4d(camera_T.T.tolist()))
 cam.GetFocalLengthAttr().Set(17.);cam.GetHorizontalApertureAttr().Set(20.955);cam.GetVerticalApertureAttr().Set(20.955*a.height/a.width);cam.GetClippingRangeAttr().Set(Gf.Vec2f(.01,100.))
 product=rep.create.render_product(str(cam.GetPath()),(a.width,a.height));rgb_annotator=rep.AnnotatorRegistry.get_annotator('rgb');rgb_annotator.attach([product])
 camera_cv=camera_T@np.diag([1.,-1.,-1.,1.])
 focal_px=17./20.955*a.width
 (OUT/'ego-camera.json').write_text(json.dumps({'width':a.width,'height':a.height,'K':[[focal_px,0,a.width/2],[0,focal_px,a.height/2],[0,0,1]],'T_world_camera_opencv':camera_cv.tolist(),'T_world_camera_usd':camera_T.tolist(),'distortion':[0,0,0,0,0],'camera_static':True},indent=2))
 errors=[];last_sample=[None]
 def frame(i):
  for n,o in objs.items():
   T=track[n+'_world'][i];q=Rotation.from_matrix(T[:3,:3]).as_quat()[[3,0,1,2]];o.set_world_pose(T[:3,3],q)
  # Isaac 4.1 retains the previous deformed-point buffer. Give each source
  # sample fresh static mesh prims, and retire the preceding sample. This
  # offline cache path makes the rendered geometry match the exported sample.
  if last_sample[0]!=i:
   if last_sample[0] is not None:stage.RemovePrim(root+f'/sample_{last_sample[0]:04d}')
   group=f'sample_{i:04d}';UsdGeom.Xform.Define(stage,root+'/'+group)
   for side in ['left','right']:
    f=human['quads'];f=f[:,::-1] if side=='left' else f
    mesh(group+'/'+side+'_hand',f,skin,human[side+'_vertices'][i])
    nf=human['nail_faces'];nf=nf[:,::-1] if side=='left' else nf
    mesh(group+'/'+side+'_nails',nf,nailmat,human[side+'_nails'][i],'none')
    mesh(group+'/'+side+'_sleeve',armfaces,cloth,arm_mesh(human[side+'_arm'][i],human[side+'_wrist_T'][i]))
    # The upstream hand mesh has an open wrist boundary. A short anatomical
    # wrist volume closes it and overlaps the sleeve, preventing a hollow cuff.
    H=human[side+'_wrist_T'][i];wrist=UsdGeom.Sphere.Define(stage,root+'/'+group+'/'+side+'_wrist');wrist.CreateRadiusAttr(1.)
    WT=H.copy();WT[:3,3]+=H[:3,1]*.004;WT[:3,:3]=H[:3,:3]@np.diag([.024,.034,.020])
    UsdGeom.Xformable(wrist.GetPrim()).AddTransformOp().Set(Gf.Matrix4d(WT.T.tolist()));UsdShade.MaterialBindingAPI.Apply(wrist.GetPrim()).Bind(skin)
   last_sample[0]=i
  rep.orchestrator.step(rt_subframes=6 if a.preview else 3,pause_timeline=True,delta_time=1/30)
  for n,o in objs.items():errors.append(float(np.linalg.norm(o.get_world_pose()[0]-track[n+'_world'][i,:3,3])))
  rgba=rgb_annotator.get_data();return rgba[:,:,:3].astype(np.uint8) if rgba.ndim==3 else None
 for _ in range(12):frame(0)
 ids=[0,110,155,230,285,410,475,560,610,775,805,843] if a.preview else range(844)
 writer=None if a.preview else imageio.get_writer(OUT/'human-ego.mp4',fps=15,codec='libx264',quality=8,macro_block_size=1)
 for i in ids:
  # Flush the deformed mesh history with the same source sample. Both passes
  # keep the official object pose fixed; only the second is encoded.
  frame(i)
  rgb=frame(i)
  if rgb is None or rgb.shape!=(a.height,a.width,3):raise RuntimeError(f'Camera not ready at frame {i}')
  if writer:writer.append_data(rgb)
  if a.preview or i in [0,155,230,475,560,805,843]:imageio.imwrite(OUT/f'ego-{i:04d}.png',rgb)
  if i%50==0:print('RENDER_FRAME',i,flush=True)
 if writer:writer.close()
 result={'preview':a.preview,'frames':len(ids),'fps':15,'source_frames':844,'max_object_position_error_m':max(errors),'eye':eye.tolist(),'target':target.tolist(),'renderer':'Isaac Sim 4.1 RTX','light_intensity_multiplier':.18,'geometry_sync':'fresh static meshes per source sample; synchronous capture; no deformed-buffer history reused','method':'ManipNet released hand mesh + custom fitted grasp templates + two-bone arm IK; no neural ManipNet inference; no MANO','physics':'kinematic visual replay; recorded rigid bodies disabled; original official object trajectories imposed'}
 (OUT/('preview-check.json' if a.preview else 'verification.json')).write_text(json.dumps(result,indent=2));print('RENDER_DONE',result,flush=True)
except BaseException:
 import traceback
 traceback.print_exc();raise
finally:app.close(wait_for_replicator=False)
