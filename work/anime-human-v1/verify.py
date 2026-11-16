import json,hashlib
import numpy as np
from scipy.spatial.transform import Rotation
from rig_model import B,Rig,Hand
a=np.load(B/'anime-animation.npz');src=np.load(B/'source/world-tracks.npz');rig=Rig();N=1507
assert len(a['source_frame'])==N
assert np.array_equal(a['source_frame'],np.arange(N))
assert np.allclose(a['video_time_s'],np.arange(N)/15,atol=1e-10)
for k in src.files:assert np.array_equal(a[k],src[k]),k
g=a['bone_world'];assert np.isfinite(g).all()
assert np.all(a['torso_lean_rad']==0)
for name in ['腰','上半身','上半身2']:
 j=rig.idx(name);assert np.allclose(g[:,j],g[0,j],atol=1e-10)

report={'frames':N,'fps':15,'duration_s':N/15,'source_objects_bitwise_equal':True,
 'source_world_tracks_sha256':hashlib.sha256((B/'source/world-tracks.npz').read_bytes()).hexdigest(),
 'animation_sha256':hashlib.sha256((B/'anime-animation.npz').read_bytes()).hexdigest(),
 'torso_lean_degrees':0.,'pelvis_and_spine_constant_upright':True,'nominal_support_plane_z_m':float(a['nominal_support_plane_z_m']),'max_arm_reach_error_m':float(a['arm_reach_error_m'].max()),'limbs':{},'cameras':{}}
assert report['max_arm_reach_error_m']<1e-5
for side in ['L','R']:
 ids=[rig.idx(n+'.'+side) for n in ['腕','ひじ','手首']];p=g[:,ids][:,:,:3,3]
 lengths=np.linalg.norm(np.diff(p,axis=1),axis=-1);rest=np.linalg.norm(np.diff(rig.rest[ids,:3,3],axis=0),axis=-1)
 foot=g[:,rig.idx('足首D.'+side),:3,3];H=a[side+'_canonical_wrist_world'];hand=Hand(rig,side)
 q=a[side+'_q'];assert np.all(q>=hand.lo-1e-6) and np.all(q<=hand.hi+1e-6)
 angles=Rotation.from_matrix(H[1:,:3,:3]@np.swapaxes(H[:-1,:3,:3],1,2)).magnitude()
 err=float(np.max(abs(lengths-rest)));assert err<1e-5
 drift=float(np.linalg.norm(foot-foot[0],axis=1).max());assert drift<1e-5
 report['limbs'][side]={'native_arm_segment_lengths_m':rest.tolist(),'max_length_error_m':err,'planted_foot_drift_m':drift,'foot_position_m':foot[0].tolist(),'max_wrist_rotation_step_deg':float(np.rad2deg(angles).max()),'max_wrist_translation_step_m':float(np.linalg.norm(np.diff(H[:,:3,3],axis=0),axis=1).max()),'max_finger_joint_step_deg':float(np.rad2deg(np.abs(np.diff(q,axis=0))).max())}
C=a['camera_world_usd'];steps=Rotation.from_matrix(C[1:,:3,:3]@np.swapaxes(C[:-1,:3,:3],1,2)).magnitude()
assert C[:,0,0].min()>.90
assert steps.max()<np.deg2rad(8)
report['cameras']={'ego_anchor':'Native left/right eye centres, fixed anatomical right axis, gaze toward original work area','max_rotation_step_deg':float(np.rad2deg(steps).max()),'max_translation_step_m':float(np.linalg.norm(np.diff(C[:,:3,3],axis=0),axis=1).max()),'no_180_degree_roll_flip':True}
(B/'motion-verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
