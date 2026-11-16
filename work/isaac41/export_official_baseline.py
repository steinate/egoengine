import argparse,json,pickle
from pathlib import Path
import numpy as np
import lmdb
p=argparse.ArgumentParser();p.add_argument('episode');p.add_argument('output');a=p.parse_args()
episode=Path(a.episode);out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
env=lmdb.open(str(episode/'lmdb'),readonly=True,lock=False)
with env.begin() as txn:
    def get(k):return np.asarray(pickle.loads(txn.get(k.encode())))
    xyz=get('pick_object_left/translation');q=get('pick_object_left/orientation')
    states=get('states.joint.position');gripper=get('states.gripper.position')
    np.savez_compressed(out/'object-and-robot-tracks.npz',object_translation_local_m=xyz,
        object_orientation_wxyz=q,robot_joint_state=states,gripper_width_m=gripper,physics_dt=1/30)
    result={'task':'official single_pick: pick up the bottle and lift','frames':len(xyz),
        'physics_dt':1/30,'official_video_fps':15,'initial_object_translation_local_m':xyz[0].tolist(),
        'final_object_translation_local_m':xyz[-1].tolist(),'max_lift_local_z_m':float(xyz[:,2].max()-xyz[0,2]),
        'final_lift_local_z_m':float(xyz[-1,2]-xyz[0,2]),'final_gripper_width_m':gripper[-1].tolist(),
        'task_config_sha256':'ef5ce562db8a49d5f10b5c2f71cbe76eeb6c7356c4a9ae3cdbfc476d5c98be55',
        'task_config_matches_upstream':True,'complete_pick_and_place':False,'source_episode':str(episode)}
    (out/'verification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
