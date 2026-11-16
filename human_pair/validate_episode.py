"""Check geometric progress of the single-bottle pick/place episode, not just exit code."""
import argparse,json
from pathlib import Path
import numpy as np
p=argparse.ArgumentParser();p.add_argument('tracks');p.add_argument('--output',required=True);a=p.parse_args()
d=np.load(a.tracks,allow_pickle=False);T=d['object_T'];xyz=T[:,:3,3];n=len(xyz)
cmd=np.asarray(d['gripper_open_command']).reshape(n,-1)[:,0]
closed=cmd<.5;idx=np.flatnonzero(closed)
result={'frames':n,'duration_s':float(n*d['dt']),'initial_position_m':xyz[0].tolist(),
        'final_position_m':xyz[-1].tolist(),'max_lift_m':float(xyz[:,2].max()-xyz[0,2]),
        'horizontal_displacement_m':float(np.linalg.norm(xyz[-1,:2]-xyz[0,:2])),
        'final_height_delta_m':float(xyz[-1,2]-xyz[0,2]),
        'close_frame':int(idx[0]) if len(idx) else None,
        'last_closed_frame':int(idx[-1]) if len(idx) else None,
        'finite':bool(all(np.isfinite(d[k]).all() for k in ['object_T','robot_joint_state','robot_joint_action']))}
checks={'has_sequence':n>30,'finite':result['finite'],'lifted':result['max_lift_m']>.04,
        'translated':result['horizontal_displacement_m']>.10,'on_table_height':abs(result['final_height_delta_m'])<.08,
        'grasp_release_command':bool(len(idx) and idx[-1]<n-1 and cmd[0]>.5 and cmd[-1]>.5)}
result['checks']=checks;result['passed']=all(checks.values())
Path(a.output).write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
raise SystemExit(0 if result['passed'] else 1)
