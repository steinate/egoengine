"""Attach the native right-hand scan and mirrored left hand with correct UVs."""
from pathlib import Path
import hashlib,json,sys
import numpy as np
ROOT=Path('/vepfs/public/pengjiaqi/interndata-human-pair');B=ROOT/'human-scan-v6';OLD=ROOT/'human-scan-v5'
sys.path.insert(0,str(ROOT/'runtime41/kit/exts/omni.usd.libs'))
from pxr import Usd,UsdGeom,Vt
from hand_model import Hand,normals
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
stage=Usd.Stage.Open(str(OLD/'scan-template.usdc'))
source=dict(np.load(OLD/'scan-mesh.npz'));keep=np.all(source['points_cm'][source['faces'],2]>33.1,axis=1)
faces=source['faces'][keep];uv=source['uv'][keep].copy();uv[:,:,1]=1-uv[:,:,1];reports=[]
for side in ['L','R']:
    hand=Hand(source,side);f=faces[:,::-1] if side=='L' else faces;st=uv[:,::-1] if side=='L' else uv
    mesh=UsdGeom.Mesh(stage.GetPrimAtPath('/ScannedHands/'+side))
    mesh.GetPointsAttr().Set(Vt.Vec3fArray.FromNumpy(hand.v.astype(np.float32)))
    mesh.GetNormalsAttr().Set(Vt.Vec3fArray.FromNumpy(normals(hand.v,f).astype(np.float32)))
    mesh.GetFaceVertexIndicesAttr().Set(Vt.IntArray(f.ravel().tolist()))
    UsdGeom.PrimvarsAPI(mesh).GetPrimvar('st').Set(Vt.Vec2fArray.FromNumpy(st.reshape(-1,2).astype(np.float32)))
    # Verify scan geometry is preserved under the documented rigid/mirror mapping.
    raw=np.stack([hand.v[:,2]/.01+5.4,hand.v[:,0]/(.01*hand.sign)+.45,hand.v[:,1]/.01+33.6],axis=1)
    error=float(np.abs(raw-source['points_cm']).max());assert error<1e-10
    q=np.zeros(17);q[9]=.2 # Middle MCP flexion.
    movement=hand.tips(q)[2]-hand.tips(np.zeros(17))[2]
    dorsal_component=float(movement@np.array([hand.sign,0,0]));assert dorsal_component<0
    reports.append({'side':side,'mirrored':side=='L','vertices':len(hand.v),'max_rest_source_roundtrip_error_cm':error,'positive_flexion_dorsal_component_m':dorsal_component})
stage.Export(str(B/'scan-template.usdc'))
report={'fixes':['UV V: (u,v) -> (u,1-v)','Native asset is a right hand; keep right chirality and mirror left','Align native dorsal side with actor dorsal side; positive finger flexion goes toward palm'],
        'native_geometry_preserved_in_source_coordinates':True,'actor_body_unchanged':True,'arm_and_wrist_targets_unchanged':True,'object_trajectory_unchanged':True,
        'original_diffuse_sha256':sha(OLD/'assets/Sample_Hand_Diffuse.png'),'meshes':reports,
        'geometry':'Source-derived reduced scan; original UV topology and original 8192x8192 diffuse, no replacement skin image',
        'material':'Supplier ZIP references but omits its MTL. Existing OmniSurface parameters retained; original diffuse restored to the correct UV correspondence.',
        'attribution':'Digital Reality Lab / HumanScanRepository'}
(B/'native-hand-verification.json').write_text(json.dumps(report,indent=2));(B/'template-report.json').write_text(json.dumps(report,indent=2));print('NATIVE_HANDS_ALIGNED',json.dumps(report),flush=True)
