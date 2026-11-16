"""Headless native NuRec/mesh validation. No image compositing or proxy splats."""
import argparse, sys, json, time, gzip, types, hashlib
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--mode',choices=['flowers','replay','hand','mixed'],default='flowers');p.add_argument('--frames',type=int,default=91);p.add_argument('--enable-schema',action='store_true');p.add_argument('--color-fix',action='store_true');p.add_argument('--diagnostic-light',action='store_true');p.add_argument('--legacy-hydra',action='store_true');p.add_argument('--preview-materials',action='store_true');p.add_argument('--isolated',action='store_true');p.add_argument('--sanitize-normals',action='store_true');p.add_argument('--tag',default='');p.add_argument('--arm',action='store_true');p.add_argument('--reuse-assets',action='store_true');args=p.parse_args()
ROOT=Path('/vepfs/public/pengjiaqi/interndata-human-pair');BASE=ROOT/'validation51';OUT=BASE/'output'/(args.mode+('-'+args.tag if args.tag else ''));OUT.mkdir(parents=True,exist_ok=True)
sys.argv=[sys.argv[0],'--allow-root','--portable-root',str(BASE/'cache/kit'),f'--/log/file={OUT}/kit.log','--/app/hydraEngine/waitIdle=true','--/app/updateOrder/checkForHydraRenderComplete=1000','--/renderer/multiGpu/enabled=false']
if args.legacy_hydra:sys.argv+=['--/app/useFabricSceneDelegate=false']
from isaacsim import SimulationApp
app=SimulationApp({'headless':True,'multi_gpu':False,'width':960,'height':540,'renderer':'RayTracedLighting','anti_aliasing':0})
try:
 import numpy as np, omni.usd, omni.kit.app, carb
 import omni.replicator.core as rep
 from pxr import Usd, UsdGeom, UsdLux, UsdShade, UsdPhysics, Sdf, Gf, Vt
 from PIL import Image
 from scipy.spatial.transform import Rotation
 settings=carb.settings.get_settings()
 if (OUT/'result.json').exists():(OUT/'result.json').unlink()
 if args.enable_schema:
  manager=omni.kit.app.get_app().get_extension_manager()
  print('SCHEMA_ENABLE',manager.set_extension_enabled_immediate('omni.usd.schema.omni_nurec_types',True),flush=True)
 print('APP_READY',flush=True)
 def save_json(name,data): (OUT/name).write_text(json.dumps(data,indent=2))
 def export_nurec(npz_or_ply,folder):
  # Use upstream 3DGRUT serialization modules unmodified, without training/GUI imports.
  repo=BASE/'3dgrut'
  for name in ['threedgrut','threedgrut.export','threedgrut.export.usd','threedgrut.export.usd.nurec']:
   mod=types.ModuleType(name);mod.__path__=[str(repo.joinpath(*name.split('.')))];sys.modules[name]=mod
  from threedgrut.export.usd.nurec.templates import fill_3dgut_template,NamedSerialized
  from threedgrut.export.usd.nurec.serializer import serialize_nurec_usd
  import msgpack
  folder.mkdir(parents=True,exist_ok=True)
  if npz_or_ply.suffix=='.ply':
   with open(npz_or_ply,'rb') as f:
    fields=[];count=None
    while True:
     line=f.readline().decode().strip()
     if line.startswith('element vertex '):count=int(line.split()[-1])
     if line.startswith('property '):
      _,dtype,n=line.split();assert dtype in ['float','float32'];fields.append((n,'<f4'))
     if line=='end_header':break
    a=np.fromfile(f,dtype=np.dtype(fields),count=count)
   get=lambda names:np.stack([a[n] for n in names],axis=1)
   data=dict(positions=get(['x','y','z']),rotations=get(['rot_'+str(i) for i in range(4)]),scales=get(['scale_'+str(i) for i in range(3)]),densities=get(['opacity']),features_albedo=get(['f_dc_'+str(i) for i in range(3)]))
   rest=sorted([n for n in a.dtype.names if n.startswith('f_rest_')],key=lambda n:int(n[7:]))
   # PLY has channel-major SH; NuRec uses coefficient-major RGB.
   data['features_specular']=get(rest).reshape(len(a),3,-1).transpose(0,2,1).reshape(len(a),-1)
  else:data=dict(np.load(npz_or_ply))
  degree=int(round(np.sqrt(data['features_specular'].shape[1]/3+1)-1))
  template=fill_3dgut_template(**data,n_active_features=degree,radiance_sph_degree=degree,global_z_order=True,density_kernel_density_clamping=True)
  payload=NamedSerialized(filename='model.nurec',serialized=gzip.compress(msgpack.packb(template),compresslevel=0))
  (folder/payload.filename).write_bytes(payload.serialized)
  usd=serialize_nurec_usd(payload,data['positions'],apply_coordinate_transform=False)
  usd.stage.GetRootLayer().Export(str(folder/'gauss.usda'))
  return folder/'gauss.usda',data['positions']
 def material(stage,path,color):
  m=UsdShade.Material.Define(stage,path);s=UsdShade.Shader.Define(stage,path+'/Shader');s.CreateIdAttr('UsdPreviewSurface');s.CreateInput('diffuseColor',Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color));s.CreateInput('roughness',Sdf.ValueTypeNames.Float).Set(.5);m.CreateSurfaceOutput().ConnectToSource(s.ConnectableAPI(),'surface');return m
 def camera(stage,eye,target,path='/World/ValidationCamera',focal=24.):
  eye=np.array(eye,dtype=float);z=eye-np.array(target);z/=np.linalg.norm(z);x=np.cross([0,0,1.],z);x/=np.linalg.norm(x);y=np.cross(z,x)
  T=np.eye(4);T[:3,:3]=np.stack([x,y,z],1);T[:3,3]=eye
  c=UsdGeom.Camera.Define(stage,path);c.AddTransformOp().Set(Gf.Matrix4d(T.T.tolist()));c.GetFocalLengthAttr().Set(focal);c.GetHorizontalApertureAttr().Set(20.955);c.GetVerticalApertureAttr().Set(20.955*540/960);c.GetClippingRangeAttr().Set(Gf.Vec2f(.01,1000))
  save_json('camera.json',{'T_world_camera_opencv':(T@np.diag([1.,-1.,-1.,1.])).tolist(),'width':960,'height':540,'focal_length':focal,'horizontal_aperture':20.955})
  return c
 def capture_setup(cam):
  prod=rep.create.render_product(str(cam.GetPath()),(960,540));rgb=rep.AnnotatorRegistry.get_annotator('rgb');rgb.attach([prod]);depth=rep.AnnotatorRegistry.get_annotator('distance_to_image_plane');depth.attach([prod]);return rgb,depth
 def capture(name,warm=8):
  for _ in range(warm):rep.orchestrator.step(rt_subframes=4,pause_timeline=True,delta_time=1/30)
  color=np.asarray(rgb.get_data())[...,:3].copy();dep=np.asarray(depth.get_data()).copy()
  assert color.shape==(540,960,3),color.shape
  Image.fromarray(color).save(OUT/(name+'.png'));np.save(OUT/(name+'-depth.npy'),dep)
  print('CAPTURE',name,float(color.mean()),float(color.std()),flush=True);return color
 if args.mode=='flowers':
  src=BASE/'assets/flowers_1/flowers_1.ply';usd,pos=export_nurec(src,OUT/'asset')
  omni.usd.get_context().open_stage(str(usd))
  for _ in range(30):app.update()
  stage=omni.usd.get_context().get_stage();g=stage.GetPrimAtPath('/World/gauss')
  lo,hi=np.percentile(pos,[1,99],axis=0);center=(lo+hi)/2;span=float(max(hi-lo));print('BOUNDS',lo,hi,flush=True)
  cube=UsdGeom.Cube.Define(stage,'/World/ControlCube');cube.CreateSizeAttr(span*.22);cube.AddTranslateOp().Set(Gf.Vec3d(*(center+np.array([span*.4,-span*.25,0]))));UsdShade.MaterialBindingAPI.Apply(cube.GetPrim()).Bind(material(stage,'/World/RedMaterial',(.8,.04,.02)))
  light=UsdLux.DomeLight.Define(stage,'/World/Light');light.CreateIntensityAttr(500)
  cam=camera(stage,center+np.array([0,-span*2,span*.25]),center)
  rgb,depth=capture_setup(cam)
  before=capture('gaussian-and-cube',30)
  UsdGeom.Imageable(g).MakeInvisible();without=capture('cube-only',12)
  UsdGeom.Imageable(g).MakeVisible();UsdGeom.Imageable(cube).MakeInvisible();only=capture('gaussian-only',12)
  diff=np.abs(before.astype(float)-without.astype(float)).mean(axis=2)
  save_json('result.json',{'mode':'native_nurec','asset':'NVIDIA public flowers_1, converted using upstream NuRec serializer; not gated Robotics-NuRec dataset','count':len(pos),'gaussian_toggle_mean_abs_rgb':float(diff.mean()),'gaussian_toggle_pixels_gt_5':int((diff>5).sum()),'gaussian_only_mean':float(only.mean()),'schema_known':bool(stage.GetPrimAtPath('/World/gauss/density_field').GetPrimDefinition()),'driver':'535.154.05','raw_bounds':[pos.min(0).tolist(),pos.max(0).tolist()],'camera_bounds':[lo.tolist(),hi.tolist()]})
  stage.Export(str(OUT/'test-scene.usda'))
 elif args.mode=='hand':
  ref=BASE/'output/ghost-reference';cfg=json.loads((ref/'camera.json').read_text());frames=[0,30,60,90]
  assets={k:export_nurec(ref/f'{k:04d}.npz',OUT/f'asset-{k:04d}')[0] for k in frames}
  omni.usd.get_context().new_stage();stage=omni.usd.get_context().get_stage();UsdGeom.Xform.Define(stage,'/World');UsdGeom.SetStageUpAxis(stage,UsdGeom.Tokens.z);UsdGeom.SetStageMetersPerUnit(stage,1.)
  T=np.array(cfg['T_world_camera_opencv'])@np.diag([1.,-1.,-1.,1.]);cam=camera(stage,T[:3,3],T[:3,3]-T[:3,2],focal=20.)
  rgb,depth=capture_setup(cam);root=stage.DefinePrim('/World/Hand','Xform');errors=[]
  if args.color_fix:
   source=Usd.Stage.Open(str(assets[frames[0]]))
   for key,value in source.GetRootLayer().customLayerData['renderSettings'].items():settings.set('/'+key.replace(':','/'),value)
  for k in frames:
   root.GetReferences().ClearReferences();root.GetReferences().AddReference(str(assets[k]),'/World')
   out=capture(f'{k:04d}',20)
   original=np.array(Image.open(ref/f'{k:04d}.png'));mask=np.load(ref/f'{k:04d}-alpha.npy')>.1;pred=np.max(out,axis=2)>10
   errors.append({'frame':k,'rgb_mae':float(np.abs(out.astype(float)-original).mean()),'foreground_rgb_mae':float(np.abs(out.astype(float)-original)[mask].mean()),'reference_mask_pixels':int(mask.sum()),'rendered_nonblack_pixels':int(pred.sum()),'mask_iou':float((mask&pred).sum()/max(1,(mask|pred).sum()))})
  save_json('result.json',{'representation':'approximate 2D surfel to thin 3D Gaussian','comparison':errors,'sh_degree':0})
 elif args.mode in ['replay','mixed']:
  src=ROOT/'outputs41/human-ego';meta=json.loads((src/'scene-meta.json').read_text());tracks=dict(np.load(src/'world-tracks.npz'))
  clean=Usd.Stage.Open(str(src/'source-scene.usdc'))
  for path in ['/Render','/Replicator','/Orchestrator',meta['robot_root']]:
   if clean.GetPrimAtPath(path):clean.RemovePrim(path)
  for prim in list(clean.Traverse()):
   if not prim.IsValid():continue
   if prim.GetTypeName()=='PhysicsScene':clean.RemovePrim(prim.GetPath());continue
   elif prim.HasAPI(UsdPhysics.RigidBodyAPI):UsdPhysics.RigidBodyAPI(prim).GetRigidBodyEnabledAttr().Set(False)
   if prim.HasAPI(UsdPhysics.CollisionAPI):UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Set(False)
   if args.sanitize_normals and prim.GetTypeName()=='Mesh':
    mesh=UsdGeom.Mesh(prim);nvert=len(mesh.GetPointsAttr().Get());nface=len(mesh.GetFaceVertexIndicesAttr().Get())
    for attr in prim.GetAttributes():
     if attr.GetName() not in ['normals','primvars:normal','primvars:normals']:continue
     value=attr.Get()
     if value is None:continue
     if len(value)==nface:attr.SetMetadata('interpolation','faceVarying')
     elif len(value)==nvert:attr.SetMetadata('interpolation','vertex')
     else:prim.RemoveProperty(attr.GetName())
  converted=[]
  if args.preview_materials:
   for pr in list(clean.Traverse()):
    if pr.GetTypeName()!='Material':continue
    shaders=[c for c in pr.GetChildren() if c.GetTypeName()=='Shader']
    if not shaders:continue
    sh=shaders[0]
    def val(key):return sh.GetAttribute('inputs:'+key).Get()
    color=val('diffuse_color_constant') or val('BaseColor_Color') or (.5,.5,.5)
    texture=val('diffuse_texture') or val('BaseColor_Tex')
    if val('IsBaseColorTex')==0:texture=None
    path=str(pr.GetPath());m=UsdShade.Material(pr)
    for output in m.GetOutputs():pr.RemoveProperty(output.GetFullName())
    shader=UsdShade.Shader.Define(clean,path+'/MigrationPreview');shader.CreateIdAttr('UsdPreviewSurface');shader.CreateInput('diffuseColor',Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*list(color)[:3]));shader.CreateInput('roughness',Sdf.ValueTypeNames.Float).Set(.55)
    if texture:
     tex=UsdShade.Shader.Define(clean,path+'/MigrationTexture');tex.CreateIdAttr('UsdUVTexture');tex.CreateInput('file',Sdf.ValueTypeNames.Asset).Set(texture);tex.CreateInput('sourceColorSpace',Sdf.ValueTypeNames.Token).Set('sRGB');tex.CreateOutput('rgb',Sdf.ValueTypeNames.Float3)
     uv=UsdShade.Shader.Define(clean,path+'/MigrationUV');uv.CreateIdAttr('UsdPrimvarReader_float2');uv.CreateInput('varname',Sdf.ValueTypeNames.Token).Set('st');uv.CreateOutput('result',Sdf.ValueTypeNames.Float2);tex.CreateInput('st',Sdf.ValueTypeNames.Float2).ConnectToSource(uv.ConnectableAPI(),'result');shader.GetInput('diffuseColor').ConnectToSource(tex.ConnectableAPI(),'rgb')
    m.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(),'surface');converted.append(path)
   save_json('material-migration.json',{'converted':converted,'note':'Legacy MDL materials replaced by UsdPreviewSurface; original diffuse textures preserved where available'})
  world_only=Usd.Stage.CreateInMemory();Sdf.CopySpec(clean.GetRootLayer(),'/World',world_only.GetRootLayer(),'/World');UsdGeom.SetStageMetersPerUnit(world_only,1.);UsdGeom.SetStageUpAxis(world_only,UsdGeom.Tokens.z);world_only.SetDefaultPrim(world_only.GetPrimAtPath('/World'));world_only.Export(str(OUT/'scene.usdc'));del clean,world_only
  if args.isolated:
   iso=Usd.Stage.CreateInMemory();UsdGeom.Xform.Define(iso,'/World');UsdGeom.SetStageMetersPerUnit(iso,1.);UsdGeom.SetStageUpAxis(iso,UsdGeom.Tokens.z)
   colors={'place_object':(.65,.65,.65),'pick_object_left1':(.12,.45,.18),'pick_object_right1':(.75,.15,.04)}
   for n,m in meta['objects'].items():
    parent=UsdGeom.Xform.Define(iso,m['prim_path']);mesh=UsdGeom.Mesh.Define(iso,m['prim_path']+'/Mesh');verts=tracks[n+'_mesh_vertices'];faces=tracks[n+'_mesh_faces'];mesh.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(verts.astype(np.float32)));mesh.CreateFaceVertexCountsAttr([3]*len(faces));mesh.CreateFaceVertexIndicesAttr(faces.ravel().tolist());mesh.CreateSubdivisionSchemeAttr('none');UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(material(iso,'/World/'+n+'_Material',colors[n]))
   table=UsdGeom.Cube.Define(iso,'/World/Table');table.CreateSizeAttr(1.);table.AddTranslateOp().Set(Gf.Vec3d(0,-.1,.70));table.AddScaleOp().Set(Gf.Vec3f(1.4,1.1,.1));UsdShade.MaterialBindingAPI.Apply(table.GetPrim()).Bind(material(iso,'/World/TableMaterial',(.32,.24,.16)))
   UsdLux.DomeLight.Define(iso,'/World/Light').CreateIntensityAttr(500.)
   iso.Export(str(OUT/'scene.usdc'));del iso
  omni.usd.get_context().open_stage(str(OUT/'scene.usdc'))
  for _ in range(40):app.update()
  from isaacsim.core.api import World
  world=World(stage_units_in_meters=1.,physics_dt=1/30,rendering_dt=1/30);world.reset()
  stage=omni.usd.get_context().get_stage()
  diag={'metadata':str(stage.GetRootLayer().customLayerData),'meters_per_unit':UsdGeom.GetStageMetersPerUnit(stage),'up_axis':str(UsdGeom.GetStageUpAxis(stage)),'lights':[],'objects':{}}
  for prim in stage.Traverse():
   intensity=prim.GetAttribute('inputs:intensity')
   if intensity and intensity.Get() is not None:
    diag['lights'].append([str(prim.GetPath()),intensity.Get(),str(prim.GetAttribute('inputs:texture:file').Get()),str(UsdGeom.Imageable(prim).ComputeVisibility())]);intensity.Set(float(intensity.Get())*.18)
  if args.diagnostic_light:
   for prim in list(stage.Traverse()):
    if prim.GetTypeName()=='DomeLight':stage.RemovePrim(prim.GetPath())
   UsdLux.DomeLight.Define(stage,'/World/DiagnosticDome').CreateIntensityAttr(500.)
  for n,m in meta['objects'].items():
   pr=stage.GetPrimAtPath(m['prim_path']);bb=UsdGeom.BBoxCache(Usd.TimeCode.Default(),['default','render']).ComputeWorldBound(pr).ComputeAlignedRange()
   diag['objects'][n]={'bounds':str(bb),'visibility':str(UsdGeom.Imageable(pr).ComputeVisibility())}
  save_json('diagnostics.json',diag)
  cam=camera(stage,[-.18,-.58,1.23],[.28,-.06,.88],focal=20.);rgb,depth=capture_setup(cam)
  if args.mode=='mixed':
   ref=BASE/'output/ghost-reference';indices=json.loads((ref/'manifest.json').read_text())['frames'][:args.frames]
   assets={k:(BASE/'output/mixed'/f'asset-{k:04d}'/'gauss.usda' if args.reuse_assets else export_nurec(ref/f'{k:04d}.npz',OUT/f'asset-{k:04d}')[0]) for k in indices}
   root=stage.DefinePrim('/World/GaussianHand','Xform')
   if args.color_fix:
    source=Usd.Stage.Open(str(assets[indices[0]]))
    for key,value in source.GetRootLayer().customLayerData['renderSettings'].items():settings.set('/'+key.replace(':','/'),value)
   if args.arm:
    motion=dict(np.load(ROOT/'gaussian-ego/output/motion.npz'));human=dict(np.load(src/'human-animation.npz'))
    nring=48;nside=32
    faces=[[j*nside+k,j*nside+(k+1)%nside,(j+1)*nside+(k+1)%nside,(j+1)*nside+k] for j in range(nring-1) for k in range(nside)]
    sleeve=UsdGeom.Mesh.Define(stage,'/World/IKSleeve');sleeve.CreateFaceVertexCountsAttr([4]*len(faces));sleeve.CreateFaceVertexIndicesAttr(np.array(faces).ravel().tolist());sleeve.CreateSubdivisionSchemeAttr('catmullClark');sleeve.CreateDoubleSidedAttr(True);UsdShade.MaterialBindingAPI.Apply(sleeve.GetPrim()).Bind(material(stage,'/World/SleeveMaterial',(.025,.05,.085)))
    def arm_vertices(sample):
     shoulder,elbow,wrist=motion['arm'][sample].copy();wrist=motion['joints'][sample,0];direction=(wrist-elbow)/np.linalg.norm(wrist-elbow);start=wrist+direction*.012
     # Continuous Catmull-Rom centerline through wrist, elbow, shoulder.
     controls=np.array([start+(start-elbow),start,elbow,shoulder,shoulder+(shoulder-elbow)])
     centers=[];radii=[]
     for u in np.linspace(0,2,nring):
      seg=min(int(u),1);t=u-seg;p0,p1,p2,p3=controls[seg:seg+4]
      centers.append(.5*((2*p1)+(-p0+p2)*t+(2*p0-5*p1+4*p2-p3)*t*t+(-p0+3*p1-3*p2+p3)*t*t*t));radii.append(np.interp(u,[0,.15,1,2],[.036,.037,.048,.065]))
     centers=np.array(centers);verts=[];axis_hint=human['right_wrist_T'][sample+420,:3,0]
     for j,(c,r) in enumerate(zip(centers,radii)):
      axis=centers[min(j+1,nring-1)]-centers[max(j-1,0)];axis/=np.linalg.norm(axis);xx=axis_hint-axis*np.dot(axis_hint,axis);xx/=np.linalg.norm(xx);yy=np.cross(axis,xx)
      for th in np.linspace(0,2*np.pi,nside,endpoint=False):verts.append(c+r*(np.cos(th)*xx+.8*np.sin(th)*yy))
     return np.asarray(verts,np.float32)
  ops={}
  for n,m in meta['objects'].items():
   xf=UsdGeom.Xformable(stage.GetPrimAtPath(m['prim_path']));xf.ClearXformOpOrder();ops[n]=xf.AddTransformOp(opSuffix='replay51')
  errors=[];angles=[];rows=[];ids=np.array(indices)+420 if args.mode=='mixed' else np.arange(420,420+args.frames);timings=[]
  for k,i in enumerate(ids):
   started=time.perf_counter()
   if args.mode=='mixed':
    root.GetReferences().ClearReferences();root.GetReferences().AddReference(str(assets[int(i)-420]),'/World')
    if args.arm:sleeve.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(arm_vertices(int(i)-420)))
   for n,op in ops.items():
    prim=op.GetAttr().GetPrim();parent=UsdGeom.Xformable(prim.GetParent()).ComputeLocalToWorldTransform(Usd.TimeCode.Default());T=tracks[n+'_world'][i];op.Set(Gf.Matrix4d(T.T.tolist())*parent.GetInverse())
    got=np.array(UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())).T
    pe=float(np.linalg.norm(got[:3,3]-T[:3,3]));ae=float(Rotation.from_matrix(got[:3,:3]@T[:3,:3].T).magnitude());errors.append(pe);angles.append(ae);rows.append([int(i),n,pe,ae])
   c=capture(f'{k:04d}',15 if k==0 else (3 if args.mode=='mixed' else 1));timings.append(time.perf_counter()-started)
   if c.std()<1:raise RuntimeError('Replay RGB is blank; geometry alone does not pass validation')
   if args.mode=='mixed' and k==10:
    UsdGeom.Imageable(root).MakeInvisible();nohand=capture('control-no-hand',3);UsdGeom.Imageable(root).MakeVisible()
    obj=stage.GetPrimAtPath(meta['objects']['pick_object_right1']['prim_path']);UsdGeom.Imageable(obj).MakeInvisible();nocube=capture('control-no-cube',3);UsdGeom.Imageable(obj).MakeVisible()
    save_json('visibility-check.json',{'source_frame':int(i),'hand_toggle_mean_abs_rgb':float(np.abs(c.astype(float)-nohand).mean()),'hand_toggle_pixels_gt5':int((np.abs(c.astype(float)-nohand).mean(2)>5).sum()),'cube_toggle_pixels_gt5':int((np.abs(c.astype(float)-nocube).mean(2)>5).sum())})
  save_json('result.json',{'frames':len(ids),'source_frames':ids.tolist(),'source_playback_fps':15,'output_fps':5 if args.mode=='mixed' else 15,'source_physics_dt':1/30,'max_position_error_m':max(errors),'max_rotation_error_rad':max(angles),'source':'official 4.1 world-tracks.npz','source_sha256':hashlib.sha256((src/'world-tracks.npz').read_bytes()).hexdigest(),'new_physics':False,'robot_hidden':True,'render_frame_seconds':timings,'arm_included':args.arm,'arm_type':'procedural continuous sleeve driven by existing shoulder/elbow/wrist IK; not a scanned avatar' if args.arm else None,'native_gaussian':args.mode=='mixed','isolated_scene':args.isolated})
  save_json('pose-errors.json',rows)
 print('VALIDATION_FINISHED',args.mode,flush=True)
except BaseException:
 import traceback;traceback.print_exc();raise
finally:app.close(wait_for_replicator=False)
