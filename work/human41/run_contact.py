"""Isaac 4.1 character contact test. Cube is dynamic and never pose-driven.

The character is animation/IK driven with kinematic collision proxies, NOT a
torque-controlled human articulation. No object attachment or hidden constraint.
"""
import sys,argparse,json,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--no-contact',action='store_true');p.add_argument('--no-render',action='store_true');p.add_argument('--feedback',action='store_true');p.add_argument('--preview',action='store_true');p.add_argument('--capture-stride',type=int,default=2);p.add_argument('--start-frame',type=int,default=0);p.add_argument('--tag',default='contact');a=p.parse_args()
ROOT=Path('/vepfs/public/pengjiaqi/interndata-human-pair');BASE=ROOT/'human41';OUT=BASE/'output'/a.tag;OUT.mkdir(exist_ok=True)
if (OUT/'result.json').exists():(OUT/'result.json').unlink()
sys.argv=[sys.argv[0],'--allow-root','--portable-root',str(ROOT/'cache41/kit'),f'--/log/file={OUT}/kit.log','--/app/hydraEngine/waitIdle=true','--/app/updateOrder/checkForHydraRenderComplete=1000','--/app/useFabricSceneDelegate=false']
from omni.isaac.kit import SimulationApp
app=SimulationApp({'headless':True,'multi_gpu':False,'width':1280,'height':720,'renderer':'RayTracedLighting','anti_aliasing':0})
try:
 import numpy as np,omni.usd,omni.physx,omni.timeline
 import omni.replicator.core as rep
 from pxr import Usd,UsdGeom,UsdSkel,UsdLux,UsdShade,UsdPhysics,PhysxSchema,PhysicsSchemaTools,Sdf,Gf,Vt
 from omni.isaac.core import World
 from omni.isaac.core.objects import DynamicCuboid,FixedCuboid
 from omni.isaac.core.materials import PhysicsMaterial,PreviewSurface
 from scipy.spatial.transform import Rotation
 from PIL import Image
 from human_control import Human
 from character_materials import repair_materials
 h=Human();plan=np.load(BASE/'output/human-plan.npz');dt=1/240
 omni.usd.get_context().new_stage();world=World(stage_units_in_meters=1.,physics_dt=dt,rendering_dt=1/30);stage=world.stage
 stage.SetTimeCodesPerSecond(30);stage.SetStartTimeCode(0);stage.SetEndTimeCode(258)
 UsdGeom.SetStageUpAxis(stage,'Z');UsdGeom.Xform.Define(stage,'/World')
 material=PhysicsMaterial('/World/ContactMaterial',static_friction=1.,dynamic_friction=1.,restitution=0.)
 table=world.scene.add(FixedCuboid('/World/Table',name='table',position=np.array([0,.55,.95]),scale=np.array([1.4,.9,.1]),color=np.array([.22,.16,.11]),physics_material=material))
 floor=world.scene.add(FixedCuboid('/World/Floor',name='floor',position=np.array([0,0,-.05]),scale=np.array([5.,5.,.1]),color=np.array([.2,.22,.25])))
 cube=world.scene.add(DynamicCuboid('/World/Cube',name='cube',position=np.array([.25,.36,1.031]),size=.06,mass=.05,color=np.array([.5,.12,.03]),physics_material=material))
 rb=PhysxSchema.PhysxRigidBodyAPI.Apply(cube.prim);rb.CreateSolverPositionIterationCountAttr(16);rb.CreateSolverVelocityIterationCountAttr(4);rb.CreateMaxDepenetrationVelocityAttr(1.)
 PhysxSchema.PhysxContactReportAPI.Apply(cube.prim).CreateThresholdAttr(0.)
 root=UsdGeom.Xform.Define(stage,'/World/Human');root.AddScaleOp().Set(Gf.Vec3f(.01));root.AddRotateZOp().Set(180.)
 asset=BASE/'assets/characters/Assets/Characters/Reallusion/Worker'
 model=stage.DefinePrim('/World/Human/Model','SkelRoot');model.GetReferences().AddReference(str(asset/'Props/Worker.usd'),'/Worker')
 anim=UsdSkel.Animation.Define(stage,'/World/Human/Control');anim.CreateJointsAttr(h.names);anim.CreateScalesAttr(Vt.Vec3hArray([Gf.Vec3h(1.)]*len(h.names)))
 for prim in [model,stage.GetPrimAtPath('/World/Human/Model/Worker')]:UsdSkel.BindingAPI.Apply(prim).CreateAnimationSourceRel().SetTargets([anim.GetPath()])
 (OUT/'materials.json').write_text(json.dumps(repair_materials(stage),indent=2))
 UsdLux.DomeLight.Define(stage,'/World/Dome').CreateIntensityAttr(700.)
 key=UsdLux.RectLight.Define(stage,'/World/Key');key.CreateIntensityAttr(1300.);key.CreateWidthAttr(2.);key.CreateHeightAttr(2.);key.AddTranslateOp().Set(Gf.Vec3d(.6,.5,3.))
 def camera(path,eye,target,focal):
  eye=np.array(eye);z=eye-np.array(target);z/=np.linalg.norm(z);x=np.cross([0,0,1],z);x/=np.linalg.norm(x);y=np.cross(z,x);T=np.eye(4);T[:3,:3]=np.stack([x,y,z],1);T[:3,3]=eye
  cam=UsdGeom.Camera.Define(stage,path);cam.AddTransformOp().Set(Gf.Matrix4d(T.T.tolist()));cam.CreateFocalLengthAttr(focal);cam.CreateHorizontalApertureAttr(36.);cam.CreateVerticalApertureAttr(20.25);cam.CreateClippingRangeAttr(Gf.Vec2f(.18 if 'ego' in path else .025,100.));return cam,T
 cameras={};products=[];annotators={};camera_info={}
 for name,eye,target,focal in [('ego',[-.035,.28,1.67],[.24,.39,1.06],28.),('observer',[1.6,2.3,1.8],[0,.18,1.0],35.)]:
  c,T=camera('/World/'+name,eye,target,focal);cameras[name]=c;camera_info[name]={'T_world_camera_opencv':(T@np.diag([1.,-1.,-1.,1.])).tolist(),'K':[[focal/36*1280,0,640],[0,focal/36*1280,360],[0,0,1]],'resolution':[1280,720]}
  if not a.no_render:
   product=rep.create.render_product(str(c.GetPath()),(1280,720));products.append(product);an=rep.AnnotatorRegistry.get_annotator('rgb');an.attach([product]);annotators[name]=an;(OUT/name).mkdir(exist_ok=True)
 (OUT/'cameras.json').write_text(json.dumps(camera_info,indent=2))
 colliders=[]
 start=h.finger_pose(plan['fingers'][a.start_frame],h.arm_pose(plan['arm_q'][a.start_frame]));_,segments,g=h.hand_geometry(start)
 for i,(aa,bb,name,k) in enumerate(segments):
  path=f'/World/HandCollision/{name}_{k}';cap=UsdGeom.Capsule.Define(stage,path);cap.CreateRadiusAttr(.009 if name=='Thumb' else .008);cap.CreateHeightAttr(float(np.linalg.norm(bb-aa)));cap.CreateAxisAttr('Z');UsdGeom.Imageable(cap).MakeInvisible()
  body=UsdPhysics.RigidBodyAPI.Apply(cap.GetPrim());body.CreateKinematicEnabledAttr(True)
  collision=UsdPhysics.CollisionAPI.Apply(cap.GetPrim());collision.CreateCollisionEnabledAttr(not a.no_contact)
  api=PhysxSchema.PhysxCollisionAPI.Apply(cap.GetPrim());api.CreateContactOffsetAttr(.001);api.CreateRestOffsetAttr(0.)
  UsdShade.MaterialBindingAPI.Apply(cap.GetPrim()).Bind(UsdShade.Material(stage.GetPrimAtPath('/World/ContactMaterial')),UsdShade.Tokens.weakerThanDescendants,'physics')
  tr=cap.AddTranslateOp();qr=cap.AddOrientOp(UsdGeom.XformOp.PrecisionDouble);colliders.append((tr,qr))
 def set_hand(local,visual,sample=0):
  tips,segs,g=h.hand_geometry(local)
  for (aa,bb,name,k),(tr,qr) in zip(segs,colliders):
   tr.Set(Gf.Vec3d(*((aa+bb)/2)));axis=(bb-aa)/np.linalg.norm(bb-aa);q=Gf.Rotation(Gf.Vec3d(0,0,1),Gf.Vec3d(*axis)).GetQuat();qr.Set(q)
  if visual:
   xyz=local[:,:3,3]*100;quats=Rotation.from_matrix(local[:,:3,:3]).as_quat()
   anim.CreateTranslationsAttr().Set(Vt.Vec3fArray.FromNumpy(xyz.astype(np.float32)),Usd.TimeCode(float(sample)));anim.CreateRotationsAttr().Set(Vt.QuatfArray([Gf.Quatf(float(q[3]),Gf.Vec3f(*map(float,q[:3]))) for q in quats]),Usd.TimeCode(float(sample)))
  return g
 set_hand(start,True);world.reset()
 contacts=[];current_step=[0];last_contacts=[0.]
 def on_contact(headers,data):
  for hd in headers:
   paths=[str(PhysicsSchemaTools.intToSdfPath(hd.actor0)),str(PhysicsSchemaTools.intToSdfPath(hd.actor1))]
   if '/World/Cube' not in paths or not any('/HandCollision/' in path for path in paths):continue
   pts=data[hd.contact_data_offset:hd.contact_data_offset+hd.num_contact_data]
   if not len(pts):continue
   sep=min(float(c.separation) for c in pts);imp=sum(float(np.linalg.norm(c.impulse)) for c in pts);contacts.append([current_step[0]*dt,paths,sep,imp]);last_contacts[0]+=imp
 sub=omni.physx.get_physx_simulation_interface().subscribe_contact_report_events(on_contact)
 # Warm rendering at zero dt; do not impose any cube transform after creation.
 if not a.no_render:
  for _ in range(8):rep.orchestrator.step(rt_subframes=4,delta_time=0.,pause_timeline=False)
 world.play();rows=[];initial_z=None;started=time.perf_counter();feedback=np.zeros(3);actual_q=plan['arm_q'][a.start_frame].copy();actual_qs=[];feedbacks=[];old_q=actual_q.copy();new_q=actual_q.copy()
 for step in range(a.start_frame*8,(len(plan['time_s'])-1)*8+1):
  current_step[0]=step;t=step*dt;u=t*30;i=min(int(u),len(plan['time_s'])-2);f=u-i
  q=plan['arm_q'][i]*(1-f)+plan['arm_q'][i+1]*f
  if step%8==0:
   if a.feedback and 1.5<t<3.4:
    position,_=cube.get_world_pose();measured=position-np.array([.25,.36,1.03]);measured[2]=0.;feedback=.7*feedback+.3*np.clip(measured,-.05,.05)
   target=plan['target_wrist'][min(step//8,len(plan['time_s'])-1)].copy();target[:3,3]+=feedback
   old_q=actual_q.copy()
   if a.feedback:new_q,_,_=h.solve_arm(target,actual_q,q)
   else:new_q=q.copy()
  blend=(step%8+1)/8;actual_q=old_q*(1-blend)+new_q*blend
  if step%8==0:actual_qs.append(actual_q.copy());feedbacks.append(feedback.copy())
  finger=plan['fingers'][i]*(1-f)+plan['fingers'][i+1]*f;local=h.finger_pose(finger,h.arm_pose(actual_q));g=set_hand(local,step%8==0,step/8)
  world.step(render=False)
  if step%8==0:
   position,orientation=cube.get_world_pose();vel=cube.get_linear_velocity();rows.append([t,*position,*orientation,*vel,last_contacts[0]]);last_contacts[0]=0.
   if initial_z is None:initial_z=float(position[2])
   if not a.no_render and step//8%a.capture_stride==0 and (not a.preview or step//8 in [0,90,150,210,240]):
    omni.timeline.get_timeline_interface().set_current_time(t)
    for _ in range(3):rep.orchestrator.step(rt_subframes=2,delta_time=0.,pause_timeline=False)
    for name,an in annotators.items():
     rgb=np.array(an.get_data())[...,:3];assert rgb.shape==(720,1280,3) and rgb.std()>1;Image.fromarray(rgb).save(OUT/name/f'{step//8//a.capture_stride:04d}.png')
   if step%240==0:print('FRAME',step//8,'t',round(t,2),'cube',position.tolist(),'contacts',len(contacts),flush=True)
 rows=np.array(rows);np.savez_compressed(OUT/'physics-tracks.npz',time_s=rows[:,0],cube_position_m=rows[:,1:4],cube_quaternion_wxyz=rows[:,4:8],cube_linear_velocity_m_s=rows[:,8:11],hand_contact_impulse_Ns=rows[:,11],arm_q=actual_qs,finger_q=plan['fingers'],feedback_translation_m=feedbacks)
 (OUT/'contacts.json').write_text(json.dumps(contacts));hold=rows[(rows[:,0]>=4.9)&(rows[:,0]<=5.7),3]
 report={'frames':len(rows),'fps':30,'physics_hz':240,'initial_cube_z_m':initial_z,'max_cube_lift_m':float(rows[:,3].max()-initial_z),'minimum_hold_lift_m':float(hold.min()-initial_z),'final_cube_z_m':float(rows[-1,3]),'hand_contact_events':len(contacts),'hand_contact_events_with_impulse':sum(r[3]>1e-8 for r in contacts),'max_contact_penetration_m':float(max([max(0,-r[2]) for r in contacts] or [0])),'success_lift_hold':bool(hold.min()-initial_z>.10 and any(r[3]>1e-8 for r in contacts)),'cube_pose_writes_after_creation':0,'object_attachment':False,'object_mass_kg':.05,'friction':1.,'hand_control':'IK animation with kinematic bone capsules; not torque-limited articulated control','feedback':a.feedback,'character':'Reallusion CC3 Worker evaluation sample','capture_stride':a.capture_stride,'video_fps':30/a.capture_stride,'rendered':not a.no_render,'contact_enabled':not a.no_contact,'wall_seconds':time.perf_counter()-started,'task_source':'new human-owned IK contact test in Isaac 4.1; not official robot policy replay'}
 (OUT/'result.json').write_text(json.dumps(report,indent=2));print('CONTACT_TEST_DONE',report,flush=True)
except BaseException:
 import traceback;traceback.print_exc();raise
finally:app.close(wait_for_replicator=False)
