"""Bake optimized human IK using the original character skinning and UVs."""
import sys,json,hashlib,argparse
from pathlib import Path
ROOT=Path('/vepfs/public/pengjiaqi/interndata-human-pair');BASE=ROOT/'human41'
sys.path.insert(0,str(ROOT/'runtime41/kit/exts/omni.usd.libs'))
from pxr import Usd,UsdSkel,UsdGeom,Gf,Vt
import numpy as np
from scipy.spatial.transform import Rotation
sys.path.insert(0,str(BASE))
from human_control import Human
from character_materials import repair_materials
h=Human();folder=ROOT/'human-natural-v4';data=np.load(folder/'human-animation.npz');h.world=data['world_transform'];out=folder/'skin-cache';out.mkdir(exist_ok=True)
asset=BASE/'assets/characters/Assets/Characters/Reallusion/Worker/Props/Worker.usd';source=Usd.Stage.Open(str(asset))
anim=UsdSkel.Animation.Define(source,'/Worker/Control');anim.CreateJointsAttr(h.names);anim.CreateScalesAttr(Vt.Vec3hArray([Gf.Vec3h(1.)]*len(h.names)))
sk=UsdSkel.Skeleton(source.GetPrimAtPath('/Worker/Worker'));UsdSkel.BindingAPI.Apply(sk.GetPrim()).CreateAnimationSourceRel().SetTargets([anim.GetPath()]);UsdSkel.BindingAPI.Apply(source.GetPrimAtPath('/Worker')).CreateAnimationSourceRel().SetTargets([anim.GetPath()])
initial=data['local'][0];initial_q=Rotation.from_matrix(initial[:,:3,:3]).as_quat()
anim.CreateTranslationsAttr(Vt.Vec3fArray.FromNumpy((initial[:,:3,3]*100).astype(np.float32)));anim.CreateRotationsAttr(Vt.QuatfArray([Gf.Quatf(float(v[3]),Gf.Vec3f(*map(float,v[:3]))) for v in initial_q]))
cache=UsdSkel.Cache();cache.Populate(UsdSkel.Root(source.GetPrimAtPath('/Worker')),Usd.PrimDefaultPredicate);query=cache.GetSkelQuery(sk)
meshes=[]
for pr in source.Traverse():
 if not pr.IsA(UsdGeom.Mesh):continue
 mesh=UsdGeom.Mesh(pr);skin=cache.GetSkinningQuery(pr)
 if not skin:continue
 counts=np.array(mesh.GetFaceVertexCountsAttr().Get());indices=np.array(mesh.GetFaceVertexIndicesAttr().Get());tris=[];start=0
 for count in counts:
  face=indices[start:start+count];tris.extend([face[0],face[k],face[k+1]] for k in range(1,int(count)-1));start+=int(count)
 mat=UsdGeom.Xformable(sk.GetPrim()).ComputeLocalToWorldTransform(Usd.TimeCode.Default())*UsdGeom.Xformable(pr).ComputeLocalToWorldTransform(Usd.TimeCode.Default()).GetInverse()
 meshes.append((str(pr.GetPath()),skin,mesh.GetPointsAttr().Get(),np.array(tris),np.array(mat)))
ap=argparse.ArgumentParser();ap.add_argument('--preview',action='store_true');args=ap.parse_args();samples=[0,137,258,433,474,780,1006,1044,1130,1331,1506] if args.preview else list(range(len(data['source_frame'])));errors=[]
for sample in samples:
 local=data['local'][sample];q=Rotation.from_matrix(local[:,:3,:3]).as_quat()
 anim.CreateTranslationsAttr().Set(Vt.Vec3fArray.FromNumpy((local[:,:3,3]*100).astype(np.float32)));anim.CreateRotationsAttr().Set(Vt.QuatfArray([Gf.Quatf(float(v[3]),Gf.Vec3f(*map(float,v[:3]))) for v in q]))
 transforms=query.ComputeSkinningTransforms();joint_matrices=np.array(query.ComputeJointSkelTransforms()).transpose(0,2,1);joint_matrices[:,:3,3]*=.01;usd_world=h.world@joint_matrices;errors.append(float(np.linalg.norm(usd_world[:,:3,3]-h.fk(local)[:,:3,3],axis=1).max()))
 result={}
 if sample==0:
  print('ANIMQUERY',query.GetAnimQuery(),flush=True);delta=np.linalg.norm(usd_world[:,:3,3]-h.fk(local)[:,:3,3],axis=1);print('JOINT_CHECK',[(h.short[k],usd_world[k,:3,3].tolist(),h.fk(local)[k,:3,3].tolist()) for k in np.argsort(delta)[-3:]],flush=True)
 for j,(path,skin,original,tris,mat) in enumerate(meshes):
  points=Vt.Vec3fArray(original);ok=skin.ComputeSkinnedPoints(transforms,points);assert ok,path
  vertices=np.array(points);vertices=(np.c_[vertices,np.ones(len(vertices))]@mat)[:,:3];normals=np.zeros_like(vertices);a,b,c=vertices[tris[:,0]],vertices[tris[:,1]],vertices[tris[:,2]];fn=np.cross(b-a,c-a)
  for k in range(3):np.add.at(normals,tris[:,k],fn)
  normals/=np.maximum(np.linalg.norm(normals,axis=1,keepdims=True),1e-12)
  result[f'points_{j}']=vertices.astype(np.float32);result[f'normals_{j}']=normals.astype(np.float32)
 np.savez_compressed(out/f"{int(data['source_frame'][sample]):04d}.npz",**result)
 if sample%30==0:print('BAKED',sample,'joint_error',errors[-1],flush=True)
assert max(errors)<1e-5,('Skinning/FK mismatch',max(errors))
repair_materials(source,root='/Worker')
for path,skin,original,tris,mat in meshes:
 pr=source.GetPrimAtPath(path);pr.RemoveAPI(UsdSkel.BindingAPI)
 for name in ['skel:skeleton','skel:animationSource','skel:blendShapeTargets']:
  if pr.GetRelationship(name):pr.GetRelationship(name).SetTargets([])
 for name in ['primvars:skel:jointIndices','primvars:skel:jointWeights','skel:blendShapes','primvars:skel:geomBindTransform']:
  if pr.GetAttribute(name):pr.GetAttribute(name).Block()
 # Normals are recomputed from the actual deformed mesh, avoiding stale bind normals.
 for name in ['primvars:normals','primvars:normal']:
  if pr.GetAttribute(name):pr.GetAttribute(name).Block()
 UsdGeom.Mesh(pr).SetNormalsInterpolation('vertex')
source.RemovePrim('/Worker/Worker');source.RemovePrim('/Worker/Control');root=source.GetPrimAtPath('/Worker');root.SetTypeName('Xform');root.RemoveAPI(UsdSkel.BindingAPI)
if root.GetRelationship('skel:animationSource'):root.GetRelationship('skel:animationSource').SetTargets([])
source.Export(str(out/'visual-template.usdc'))
report={'source_animation':str(folder/'human-animation.npz'),'source_sha256':hashlib.sha256((folder/'human-animation.npz').read_bytes()).hexdigest(),'samples':data['source_frame'][samples].tolist(),'fps':15,'mesh_paths':[m[0] for m in meshes],'max_usd_fk_position_error_m':max(errors),'method':'CPU UsdSkel skinning of original character mesh; original UVs and PBR textures retained; area-weighted vertex normals recomputed; per-frame static geometry for Isaac4.1 rendering','world_transform':h.world.tolist()}
(out/'manifest.json').write_text(json.dumps(report,indent=2));print('BAKE_DONE',len(samples),max(errors),flush=True)
