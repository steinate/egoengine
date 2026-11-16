"""Correct the ZBrush image/UV V convention; preserve scan geometry and actor."""
from pathlib import Path
import sys, hashlib, json, shutil
import numpy as np
ROOT=Path('/vepfs/public/pengjiaqi/interndata-human-pair')
B=ROOT/'human-scan-v6'; OLD=ROOT/'human-scan-v5';B.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT/'runtime41/kit/exts/omni.usd.libs'))
from pxr import Usd,UsdGeom,Vt
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for name in ['source','scan-cache','scan-animation.npz','heat-weights.npz','hand_model.py',
             'ego-body-template.usdc','visual-body-template.usdc','contact-initialization.npz',
             'replay-contract.json','cache-verification.json','download.json','scan-inspection.json',
             'scan-fit-report.json','surface-contact-report.json','tray-contact-report.json',
             'final-motion-report.json']:
    target=B/name
    if name.endswith('.json'):
        if target.is_symlink():target.unlink()
        shutil.copy2(OLD/name,target)
        continue
    if not target.exists():target.symlink_to(OLD/name, target_is_directory=(OLD/name).is_dir())
stage=Usd.Stage.Open(str(OLD/'scan-template.usdc')); details=[]
for side in ['L','R']:
    mesh=UsdGeom.Mesh(stage.GetPrimAtPath('/ScannedHands/'+side))
    pv=UsdGeom.PrimvarsAPI(mesh).GetPrimvar('st'); before=np.array(pv.Get())
    after=before.copy();after[:,1]=1-before[:,1]
    pv.Set(Vt.Vec2fArray.FromNumpy(after.astype(np.float32)))
    details.append({'side':side,'uv_corners':len(after),'change':'(u,v) -> (u,1-v)',
                    'u_unchanged':bool(np.array_equal(before[:,0],after[:,0]))})
stage.Export(str(B/'scan-template.usdc'))
new=Usd.Stage.Open(str(B/'scan-template.usdc'))
original=Usd.Stage.Open(str(OLD/'scan-template.usdc'))
for side in ['L','R']:
    a=UsdGeom.Mesh(new.GetPrimAtPath('/ScannedHands/'+side))
    b=UsdGeom.Mesh(original.GetPrimAtPath('/ScannedHands/'+side))
    for getter in ['GetPointsAttr','GetNormalsAttr','GetFaceVertexIndicesAttr','GetFaceVertexCountsAttr']:
        assert np.array_equal(getattr(a,getter)().Get(),getattr(b,getter)().Get())
report={'fix':'ZBrush supplied image requires vertical UV conversion',
        'geometry_and_normals_unchanged':True,'actor_body_unchanged':True,
        'hand_animation_unchanged':True,'object_trajectory_unchanged':True,
        'original_diffuse_sha256':sha(OLD/'assets/Sample_Hand_Diffuse.png'),
        'original_scan_archive_sha256':sha(OLD/'downloads/Sample_Hand_CleanScan.zip'),
        'scan_animation_sha256':sha(OLD/'scan-animation.npz'),'meshes':details,
        'asset':'Digital Reality Lab / HumanScanRepository original scanned hand and 8K diffuse; existing scan-derived reduced mesh, opposite hand mirrored',
        'note':'The supplier archive does not include the referenced MTL. Existing shader parameters stay unchanged; only UV V is corrected.'}
(B/'native-uv-verification.json').write_text(json.dumps(report,indent=2))
(B/'template-report.json').write_text(json.dumps(report,indent=2))
print('NATIVE_UV_FIXED',json.dumps(report),flush=True)
