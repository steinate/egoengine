import sys,json,hashlib,csv
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
ROOT=Path('/vepfs/public/pengjiaqi/interndata-human-pair');BASE=ROOT/'human-ik-v2';OUT=BASE/'delivery';OUT.mkdir(exist_ok=True);sys.path.insert(0,str(ROOT/'human41'))
from human_control import Human
h=Human();a=np.load(BASE/'human-animation.npz');src=ROOT/'outputs41/human-ego/world-tracks.npz';source=np.load(src);N=len(a['source_frame']);assert N==844 and np.array_equal(a['source_frame'],np.arange(844)) and np.array_equal(a['video_time_s'],np.arange(844)/15)
objects=['place_object','pick_object_left1','pick_object_right1'];same={n:bool(np.array_equal(a[n+'_world'],source[n+'_world'])) for n in objects};assert all(same.values())
h.world=a['world_transform'];g=np.array([h.fk(p) for p in a['local']]);wrists=g[:,[h.idx('L_Hand'),h.idx('R_Hand')]];errs=np.linalg.norm(wrists[:,:,:3,3]-a['wrist_targets'][:,:,:3,3],axis=-1);rotation_error=Rotation.from_matrix((np.swapaxes(wrists[:,:,:3,:3],-1,-2)@a['wrist_targets'][:,:,:3,:3]).reshape(-1,3,3)).magnitude();assert errs.max()<.005 and rotation_error.max()<np.deg2rad(2)
def posture(data):
 h.world=data['world_transform'];G=np.array([h.fk(p) for p in data['local']]);knees=[];posterior=[];medial=[];length=[];footdrift=[]
 for side,sign in [('L',-1),('R',1)]:
  S,E,W=G[:,h.idx(side+'_Upperarm'),:3,3],G[:,h.idx(side+'_Forearm'),:3,3],G[:,h.idx(side+'_Hand'),:3,3];posterior.extend(S[:,1]-E[:,1]);medial.extend(sign*(S[:,0]-E[:,0]));length.extend([float(np.ptp(np.linalg.norm(E-S,axis=1))),float(np.ptp(np.linalg.norm(W-E,axis=1)))])
  A,B,C=G[:,h.idx(side+'_Thigh'),:3,3],G[:,h.idx(side+'_Calf'),:3,3],G[:,h.idx(side+'_Foot'),:3,3];u=B-A;v=C-B;knees.extend(np.rad2deg(np.arccos(np.clip(np.sum(u*v,axis=1)/np.linalg.norm(u,axis=1)/np.linalg.norm(v,axis=1),-1,1))));footdrift.append(float(np.linalg.norm(C-C[0],axis=1).max()))
 return {'knee_flexion_degrees':[float(min(knees)),float(max(knees))],'max_elbow_posterior_to_shoulder_m':float(max(posterior)),'max_elbow_medial_to_shoulder_m':float(max(medial)),'max_arm_bone_length_variation_m':max(length),'max_foot_position_drift_m':max(footdrift),'pelvis_height_m':float(G[0,h.idx('Hip'),2,3])}
newstats=posture(a);old=np.load(ROOT/'paired-human-ego/human-animation.npz');oldstats=posture(old);h.world=a['world_transform'];assert newstats['max_foot_position_drift_m']<1e-6
contact={}
for name,side,obj,start,end in [('left_cube',0,'pick_object_left1',135,291),('right_cube',1,'pick_object_right1',445,615),('left_tray',0,'place_object',708,843),('right_tray',1,'place_object',708,843)]:
 M=np.linalg.inv(a[obj+'_world'][start:end+1])@wrists[start:end+1,side];contact[name]={'relative_translation_drift_m':float(np.max(np.linalg.norm(M[:,:3,3]-M[0,:3,3],axis=1))),'relative_rotation_drift_degrees':float(np.max(Rotation.from_matrix(M[0,:3,:3].T@M[:,:3,:3]).magnitude())*180/np.pi)}
 assert contact[name]['relative_translation_drift_m']<.005
export={n+'_world':a[n+'_world'] for n in objects};export.update(source_frame=a['source_frame'],video_time_s=a['video_time_s'],left_hand_world=wrists[:,0],right_hand_world=wrists[:,1],camera_world_usd=a['camera_world_usd'],left_elbow_world=g[:,h.idx('L_Forearm'),:3,3],right_elbow_world=g[:,h.idx('R_Forearm'),:3,3],arm_q=a['arm_q'],hip_lean_rad=a['hip_lean_rad'])
np.savez_compressed(OUT/'paired-world-trajectories.npz',**export)
report={'frames':N,'fps':15,'duration_s':N/15,'objects_bitwise_equal_to_official_source':same,'source_world_tracks_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'source_animation_sha256':hashlib.sha256((BASE/'human-animation.npz').read_bytes()).hexdigest(),'original_ik':oldstats,'optimized_ik':newstats,'max_wrist_target_position_error_m':float(errs.max()),'max_wrist_target_orientation_error_degrees':float(rotation_error.max()*180/np.pi),'grasp_contact_drift':contact,'maximum_absolute_wrist_deviation_degrees':float(np.max(np.abs(np.rad2deg(a['arm_q'][:,:,7])))),'maximum_absolute_wrist_flexion_degrees':float(np.max(np.abs(np.rad2deg(a['arm_q'][:,:,8])))),'physics':'Visual retargeting; source object motion imposed exactly; not a new human contact dynamics simulation','naturalness_limit':'Joint limits, mocap pose references and rig-compatible twist distribution improve pose quality; no claim of validated physical balance or photorealism'}
(OUT/'ik-and-pair-verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
