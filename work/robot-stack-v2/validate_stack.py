"""Independent geometric/temporal acceptance, using recorded physics poses."""
import argparse,json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as R
p=argparse.ArgumentParser();p.add_argument('trial');a=p.parse_args()
folder=Path(a.trial);d=np.load(folder/'diagnostic-tracks.npz')
lo=d['pick_object_left1'];up=d['pick_object_right1'];tray=d['place_object'];n=len(lo)
delta=up[:,:3]-lo[:,:3]
rotation={name:R.from_quat(d[name][:,[4,5,6,3]]).as_matrix() for name in ['pick_object_left1','pick_object_right1','place_object']}
tilt={name:np.rad2deg(np.arccos(np.clip(np.abs(rotation[name][:,2,2]),0,1))) for name in ['pick_object_left1','pick_object_right1']}
xy=np.linalg.norm(delta[:,:2],axis=1)
stack=(xy<.012)&(delta[:,2]>.048)&(delta[:,2]<.067)&(tilt['pick_object_left1']<8)&(tilt['pick_object_right1']<8)
events=json.loads((folder/'events.json').read_text())
retract_done=next((e['frame'] for e in events if 'right:Gripper_Action' in e['phase'] and 'close_gripper' not in e['phase']),None)
liftstart=next((e['frame'] for e in events if 'left:Heuristic_Skill' in e['phase'] and 'right:Heuristic_Skill' in e['phase']),None)
holds=next((e['frame'] for e in events if liftstart is not None and e['frame']>liftstart and 'left:Gripper_Action' in e['phase']),None)
def summary(start,end):
    s=slice(start,end)
    return {'start':start,'end_exclusive':end,'all_frames_stacked':bool(stack[s].all()),
            'max_xy_offset_m':float(xy[s].max()),'height_difference_range_m':[float(delta[s,2].min()),float(delta[s,2].max())],
            'max_cube_tilt_deg':{k:float(v[s].max()) for k,v in tilt.items()}}
result={'frames':n,'physics_dt_s':1/30,'video_fps':15,'task_variant':'official pipeline with stable_place task-local skill',
        'after_retract_frame':retract_done,'tray_lift_start_frame':liftstart,'hold_start_frame':holds,
        'last_60_frames':summary(max(0,n-60),n),'final_delta_m':delta[-1].tolist(),
        'tray_final_lift_m':float(tray[-1,2]-tray[0,2]),
        'official_workflow_frames':json.loads((folder/'result.json').read_text())['official_workflow_frames']}
if retract_done is not None:
    result['post_retract_to_end']=summary(retract_done,n)
if holds is not None:
    relative=np.einsum('nji,nj->ni',rotation['place_object'],up[:,:3]-tray[:,:3])
    result['final_hold_relative_drift_m']=float(np.linalg.norm(relative[holds:]-relative[holds],axis=1).max())
result['passed']=bool(result['official_workflow_frames']>0 and retract_done is not None and holds is not None
    and n-holds>=55 and stack[retract_done:].all() and result['tray_final_lift_m']>.12
    and result.get('final_hold_relative_drift_m',1)<.006)
(folder/'stack-validation.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
