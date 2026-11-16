from pathlib import Path
import json,sys,numpy as np,os
sys.path.insert(0,"/vepfs/public/pengjiaqi/interndata-human-pair/runtime41/kit/exts/omni.usd.libs")
from pxr import Usd,UsdSkel,UsdGeom,Vt
B=Path('/vepfs/public/pengjiaqi/interndata-human-pair/avatar-assets-v1');reports=[]
for spec in json.loads((B/'asset-drive-verification.json').read_text()):
    if os.environ.get('ASSET_ONLY') and spec['name']!=os.environ['ASSET_ONLY']:continue
    source=Usd.Stage.Open(spec['usd']);folder=Path(spec['usd']).parent;out=folder/'cache';out.mkdir(exist_ok=True)
    cache=UsdSkel.Cache()
    for pr in source.Traverse():
        if pr.IsA(UsdSkel.Root):cache.Populate(UsdSkel.Root(pr),Usd.PrimDefaultPredicate)
    skels=[UsdSkel.Skeleton(p) for p in source.Traverse() if p.IsA(UsdSkel.Skeleton)];assert len(skels)==1
    sk=skels[0];q=cache.GetSkelQuery(sk);joints=list(q.GetJointOrder());meshes=[]
    for pr in source.Traverse():
        if not pr.IsA(UsdGeom.Mesh):continue
        mesh=UsdGeom.Mesh(pr);skin=cache.GetSkinningQuery(pr)
        if not skin:continue
        counts=np.array(mesh.GetFaceVertexCountsAttr().Get());inds=np.array(mesh.GetFaceVertexIndicesAttr().Get());tri=[];start=0
        for c in counts:
            f=inds[start:start+c];tri.extend([f[0],f[k],f[k+1]] for k in range(1,int(c)-1));start+=int(c)
        mat=UsdGeom.Xformable(sk.GetPrim()).ComputeLocalToWorldTransform(Usd.TimeCode(0))*UsdGeom.Xformable(pr).ComputeLocalToWorldTransform(Usd.TimeCode(0)).GetInverse()
        meshes.append((str(pr.GetPath()),skin,mesh.GetPointsAttr().Get(),np.array(tri),np.array(mat)))
    assert meshes;bounds=[];position_change=[];initial=None
    for frame in range(61):
        t=Usd.TimeCode(frame);trans=q.ComputeSkinningTransforms(t);data={};allpoints=[]
        for j,(path,skin,original,tri,mat) in enumerate(meshes):
            points=Vt.Vec3fArray(original);assert skin.ComputeSkinnedPoints(trans,points)
            v=np.array(points);v=(np.c_[v,np.ones(len(v))]@mat)[:,:3];normal=np.zeros_like(v);a,b,c=v[tri[:,0]],v[tri[:,1]],v[tri[:,2]];fn=np.cross(b-a,c-a)
            for k in range(3):np.add.at(normal,tri[:,k],fn)
            normal/=np.maximum(np.linalg.norm(normal,axis=1,keepdims=True),1e-12)
            data[f'points_{j}']=v.astype(np.float32);data[f'normals_{j}']=normal.astype(np.float32);world=np.array(UsdGeom.Xformable(source.GetPrimAtPath(path)).ComputeLocalToWorldTransform(t));allpoints.append((np.c_[v,np.ones(len(v))]@world)[:,:3])
        ap=np.concatenate(allpoints);assert np.isfinite(ap).all()
        if initial is None:initial=ap.copy()
        position_change.append(float(np.linalg.norm(ap-initial,axis=1).max()));bounds.append([ap.min(0).tolist(),ap.max(0).tolist()]);np.savez_compressed(out/f'{frame:04d}.npz',**data)
    for pr in list(source.Traverse()):
        if pr.HasAPI(UsdSkel.BindingAPI):pr.RemoveAPI(UsdSkel.BindingAPI)
        for rn in ['skel:skeleton','skel:animationSource','skel:blendShapeTargets']:
            if pr.GetRelationship(rn):pr.GetRelationship(rn).SetTargets([])
        for an in ['primvars:skel:jointIndices','primvars:skel:jointWeights','skel:blendShapes','primvars:skel:geomBindTransform']:
            if pr.GetAttribute(an):pr.GetAttribute(an).Block()
        if pr.IsA(UsdSkel.Root):pr.SetTypeName('Xform')
    remove=[str(pr.GetPath()) for pr in source.Traverse() if pr.IsA(UsdSkel.Skeleton) or pr.IsA(UsdSkel.Animation)]
    for path in sorted(remove,key=len,reverse=True):
        if source.GetPrimAtPath(path):source.RemovePrim(path)
    for path,skin,original,tri,mat in meshes:
        mesh=UsdGeom.Mesh(source.GetPrimAtPath(path));mesh.SetNormalsInterpolation('vertex')
        for n in ['primvars:normals','primvars:normal']:
            if mesh.GetPrim().GetAttribute(n):mesh.GetPrim().GetAttribute(n).Block()
    source.Export(str(folder/'visual-template.usdc'))
    report={'name':spec['name'],'joints':joints,'mesh_paths':[m[0] for m in meshes],'frames':61,'bounds':bounds,'max_vertex_motion_m':max(position_change),'source_usd':spec['usd'],'visual_template':str(folder/'visual-template.usdc'),'method':'CPU UsdSkel deformation for Isaac Sim 4.1 mesh playback; source rigged USD retained.'}
    (folder/'manifest.json').write_text(json.dumps(report,indent=2));reports.append(report);print('BAKED',spec['name'],len(joints),len(meshes),max(position_change),flush=True)
if os.environ.get('ASSET_ONLY'):
    previous=json.loads((B/'usd-compatibility.json').read_text());replace={r['name']:r for r in reports};reports=[replace.get(r['name'],r) for r in previous]
(B/'usd-compatibility.json').write_text(json.dumps(reports,indent=2))
