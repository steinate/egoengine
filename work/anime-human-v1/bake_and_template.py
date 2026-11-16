"""Preserve native PMX geometry, UVs, weights and materials in USD replay."""
import sys,json,hashlib,argparse
from pathlib import Path
import numpy as np
B=Path(__file__).resolve().parent;ROOT=B.parent
sys.path.insert(0,str(ROOT/'runtime41/kit/exts/omni.usd.libs'))
from pxr import Usd,UsdGeom,UsdShade,Sdf,Gf,Vt
p=argparse.ArgumentParser();p.add_argument('--frames',default='');a=p.parse_args()
data=np.load(B/'anime-animation.npz');mesh=np.load(B/'amber-mesh.npz');materials=json.loads((B/'materials.json').read_text())
source=np.load(B/'source/world-tracks.npz')
for k in source.files:assert np.array_equal(source[k],data[k]),k
digest=hashlib.sha256((B/'anime-animation.npz').read_bytes()).hexdigest();v=mesh['points']*1.10;faces=mesh['faces'];weights=mesh['weights'];ids=mesh['ids']
def normals(v,f):
 n=np.zeros_like(v);face=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]])
 for k in range(3):np.add.at(n,f[:,k],face)
 return n/np.maximum(np.linalg.norm(n,axis=1,keepdims=True),1e-12)
for view in ['front','ego']:
 stage=Usd.Stage.CreateNew(str(B/(view+'-template.usdc')));root=UsdGeom.Xform.Define(stage,'/Amber');stage.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageMetersPerUnit(stage,1.);UsdGeom.SetStageUpAxis(stage,UsdGeom.Tokens.z)
 fmask=np.ones(len(faces),bool) if view=='front' else mesh['ego_keep']
 # Alpha-zero expression overlays are hidden in the original PMX rest state.
 fmask&=np.array([materials[i]['alpha']>.01 for i in mesh['material']])
 f=faces[fmask];m=UsdGeom.Mesh.Define(stage,'/Amber/Body');m.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(v.astype(np.float32)));m.CreateFaceVertexCountsAttr([3]*len(f));m.CreateFaceVertexIndicesAttr(f.ravel().tolist());m.CreateSubdivisionSchemeAttr('none');m.CreateDoubleSidedAttr(True)
 m.CreateNormalsAttr(Vt.Vec3fArray.FromNumpy(normals(v,f).astype(np.float32)));m.SetNormalsInterpolation('vertex')
 uv=mesh['uv'][fmask].reshape(-1,2);UsdGeom.PrimvarsAPI(m).CreatePrimvar('st',Sdf.ValueTypeNames.TexCoord2fArray,UsdGeom.Tokens.faceVarying).Set(Vt.Vec2fArray.FromNumpy(uv.astype(np.float32)))
 for i,info in enumerate(materials):
  ind=np.where(mesh['material'][fmask]==i)[0]
  if not len(ind):continue
  material=UsdShade.Material.Define(stage,f'/Amber/Looks/M{i}');shader=UsdShade.Shader.Define(stage,f'/Amber/Looks/M{i}/Surface');shader.CreateIdAttr('UsdPreviewSurface')
  shader.CreateInput('roughness',Sdf.ValueTypeNames.Float).Set(.8);shader.CreateInput('metallic',Sdf.ValueTypeNames.Float).Set(0.)
  shader.CreateInput('diffuseColor',Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*info['rgba'][:3]));shader.CreateInput('opacity',Sdf.ValueTypeNames.Float).Set(info['alpha'])
  if info.get('texture'):
   tex=UsdShade.Shader.Define(stage,f'/Amber/Looks/M{i}/Texture');tex.CreateIdAttr('UsdUVTexture');tex.CreateInput('file',Sdf.ValueTypeNames.Asset).Set(str(B/info['texture']));tex.CreateInput('sourceColorSpace',Sdf.ValueTypeNames.Token).Set('sRGB')
   uvread=UsdShade.Shader.Define(stage,f'/Amber/Looks/M{i}/UV');uvread.CreateIdAttr('UsdPrimvarReader_float2');uvread.CreateInput('varname',Sdf.ValueTypeNames.Token).Set('st');uvread.CreateOutput('result',Sdf.ValueTypeNames.Float2)
   tex.CreateInput('st',Sdf.ValueTypeNames.Float2).ConnectToSource(uvread.ConnectableAPI(),'result');tex.CreateOutput('rgb',Sdf.ValueTypeNames.Float3);tex.CreateOutput('a',Sdf.ValueTypeNames.Float)
   shader.GetInput('diffuseColor').ConnectToSource(tex.ConnectableAPI(),'rgb');shader.GetInput('opacity').ConnectToSource(tex.ConnectableAPI(),'a');shader.CreateInput('opacityThreshold',Sdf.ValueTypeNames.Float).Set(.1)
  shader.CreateOutput('surface',Sdf.ValueTypeNames.Token);material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(),'surface')
  sub=UsdGeom.Subset.CreateGeomSubset(m,f'Part{i}',UsdGeom.Tokens.face,Vt.IntArray(ind.tolist()),'materialBind',UsdGeom.Tokens.partition);UsdShade.MaterialBindingAPI.Apply(sub.GetPrim()).Bind(material)
 stage.GetRootLayer().Save()
out=B/'skin-cache';out.mkdir(exist_ok=True);frames=[int(i) for i in a.frames.split(',')] if a.frames else range(len(data['source_frame']));inverse=np.linalg.inv(data['rest']);maxstep=0;last=None
for i in frames:
 D=data['bone_world'][i]@inverse;T=(D[ids]*weights[...,None,None]).sum(1);points=np.einsum('nij,nj->ni',T[:,:3,:3],v)+T[:,:3,3];n=normals(points,faces)
 assert np.isfinite(points).all()
 if last is not None and i==last[0]+1:maxstep=max(maxstep,float(np.linalg.norm(points-last[1],axis=1).max()))
 last=(i,points.copy());np.savez(out/f'{i:04d}.npz',points=points.astype(np.float32),normals=n.astype(np.float32),source_frame=i,animation_sha256=digest)
 if i%100==0:print('BAKED',i,flush=True)
(out/'manifest.json').write_text(json.dumps({'frames':list(frames),'animation_sha256':digest,'vertices':len(v),'faces':len(faces),'max_vertex_step_m':maxstep,'objects_exact':True,'skinning':'Original PMX weights, linear blend skinning; native 208-bone rig'},indent=2))
print('BAKE_DONE',len(list(frames)),maxstep,flush=True)
