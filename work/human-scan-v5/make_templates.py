"""Prepare scan skin and hide the replaced legacy hands in both body views."""
import sys,json,numpy as np
from pathlib import Path
ROOT=Path('/vepfs/public/pengjiaqi/interndata-human-pair');B=ROOT/'human-scan-v5';OLD=ROOT/'human-natural-v4'
sys.path.insert(0,str(ROOT/'runtime41/kit/exts/omni.usd.libs'));sys.path.insert(0,str(ROOT/'human41'))
from pxr import Usd,UsdGeom,UsdShade,Sdf,Gf,Vt
from human_control import Human
from hand_model import Hand,normals
h=Human();h.world=np.eye(4);rest=h.fk(h.rest);changes=[]
for kind in ['visual','ego']:
 stage=Usd.Stage.Open(str(OLD/f'skin-cache/{kind}-template.usdc'))
 for prim in stage.Traverse():
  if not prim.IsA(UsdGeom.Mesh) or 'CC_Base_Body' not in str(prim.GetPath()):continue
  m=UsdGeom.Mesh(prim);v=np.array(m.GetPointsAttr().Get());world=np.array(UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default()));p=(np.c_[v,np.ones(len(v))]@world)[:,:3]*.01
  remove=np.zeros(len(v),bool)
  for side in ['L','R']:
   inv=np.linalg.inv(rest[h.idx(side+'_Hand')]);loc=p@inv[:3,:3].T+inv[:3,3]
   remove|=(loc[:,1]>-.005)&(np.linalg.norm(loc,axis=1)<.30)
  counts=np.array(m.GetFaceVertexCountsAttr().Get());indices=np.array(m.GetFaceVertexIndicesAttr().Get());keep=[];corners=[];offset=0
  for i,n in enumerate(counts):
   if not remove[indices[offset:offset+n]].any():keep.append(i);corners.extend(range(offset,offset+n))
   offset+=n
  keep=np.array(keep);corners=np.array(corners);mapping=np.full(len(counts),-1);mapping[keep]=np.arange(len(keep))
  for pv in UsdGeom.PrimvarsAPI(m).GetPrimvars():
   if str(pv.GetInterpolation())!='faceVarying':continue
   if pv.IsIndexed():pv.SetIndices(Vt.IntArray(np.array(pv.GetIndices())[corners].tolist()))
   else:
    vals=pv.Get();pv.Set(type(vals)([vals[int(i)] for i in corners]))
  for subset in UsdGeom.Subset.GetAllGeomSubsets(m):
   old=np.array(subset.GetIndicesAttr().Get());new=mapping[old];subset.GetIndicesAttr().Set(Vt.IntArray(new[new>=0].tolist()))
  m.GetFaceVertexCountsAttr().Set(Vt.IntArray(counts[keep].tolist()));m.GetFaceVertexIndicesAttr().Set(Vt.IntArray(indices[corners].tolist()))
  changes.append({'view':kind,'mesh':str(prim.GetPath()),'removed_faces':len(counts)-len(keep),'remaining_faces':len(keep)})
 stage.Export(str(B/f'{kind}-body-template.usdc'))
stage=Usd.Stage.CreateNew(str(B/'scan-template.usdc'));UsdGeom.SetStageMetersPerUnit(stage,1.);UsdGeom.SetStageUpAxis(stage,'Z');root=UsdGeom.Xform.Define(stage,'/ScannedHands');stage.SetDefaultPrim(root.GetPrim())
mat=UsdShade.Material.Define(stage,'/ScannedHands/Skin');shader=UsdShade.Shader.Define(stage,'/ScannedHands/Skin/Surface');shader.CreateImplementationSourceAttr('sourceAsset');shader.SetSourceAsset(Sdf.AssetPath('OmniSurface.mdl'),'mdl');shader.SetSourceAssetSubIdentifier('OmniSurface','mdl');shader.CreateOutput('out',Sdf.ValueTypeNames.Token)
for key,value in {'diffuse_reflection_weight':.7,'specular_reflection_weight':1.,'specular_reflection_roughness':.48,'specular_reflection_ior':1.4,'subsurface_weight':.3,'subsurface_scale':.001,'metalness':0.}.items():shader.CreateInput(key,Sdf.ValueTypeNames.Float).Set(value)
shader.CreateInput('enable_diffuse_transmission',Sdf.ValueTypeNames.Bool).Set(True)
shader.CreateInput('subsurface_scattering_color',Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(1.,.45,.2))
for key in ['diffuse_reflection_color_image','subsurface_transmission_color_image']:shader.CreateInput(key,Sdf.ValueTypeNames.Asset).Set(Sdf.AssetPath(str(B/'assets/Sample_Hand_Diffuse.png')))
for key in ['surface','displacement','volume']:mat.CreateOutput('mdl:'+key,Sdf.ValueTypeNames.Token).ConnectToSource(shader.ConnectableAPI(),'out')
mesh=dict(np.load(B/'scan-mesh.npz'));keep=np.all(mesh['points_cm'][mesh['faces'],2]>33.1,axis=1);mesh['faces']=mesh['faces'][keep];mesh['uv']=mesh['uv'][keep]
for side in ['L','R']:
 hand=Hand(mesh,side);faces=mesh['faces'][:,::-1] if side=='R' else mesh['faces'];uv=mesh['uv'][:,::-1] if side=='R' else mesh['uv']
 m=UsdGeom.Mesh.Define(stage,'/ScannedHands/'+side);m.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(hand.v.astype(np.float32)));m.CreateFaceVertexCountsAttr(Vt.IntArray([3]*len(faces)));m.CreateFaceVertexIndicesAttr(Vt.IntArray(faces.ravel().tolist()));m.CreateSubdivisionSchemeAttr('none');m.CreateDoubleSidedAttr(False)
 m.CreateNormalsAttr(Vt.Vec3fArray.FromNumpy(normals(hand.v,faces).astype(np.float32)));m.SetNormalsInterpolation('vertex');UsdGeom.PrimvarsAPI(m).CreatePrimvar('st',Sdf.ValueTypeNames.TexCoord2fArray,'faceVarying').Set(Vt.Vec2fArray.FromNumpy(uv.reshape(-1,2).astype(np.float32)));UsdShade.MaterialBindingAPI.Apply(m.GetPrim()).Bind(mat)
stage.GetRootLayer().Save();(B/'template-report.json').write_text(json.dumps({'body_mask':changes,'skin':'OmniSurface, source 8K diffuse, dielectric specular and 1 mm SSS radius scale','source':'Digital Reality Lab Hand Scan Sample','note':'Single scanned hand mirrored; source scan geometry only reduced, not procedural synthetic geometry'},indent=2));print('TEMPLATES_DONE',changes,flush=True)
