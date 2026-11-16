"""Export world-space object/EE/TCP tracks from a trusted patched plan pickle."""
import argparse,json,pickle
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation

def main():
    ap=argparse.ArgumentParser();ap.add_argument('plan');ap.add_argument('--object',default='pick_object_left')
    ap.add_argument('--robot',default='franka');ap.add_argument('--output',required=True)
    a=ap.parse_args();path=Path(a.plan)
    cfg,rec,log=map(pickle.loads,pickle.loads(path.read_bytes()))
    if rec.get('mode')!='prim_pose':raise ValueError('Exporter currently requires prim_pose mode')
    meta=json.loads(path.with_suffix('.meta.json').read_text());paths=rec.get('prim_paths')
    if paths!=meta['prim_paths']:raise ValueError('Missing/mismatched prim path manifest')
    def matrices(prim):
        idx=paths.index(prim)
        p=np.array([f[idx][0] for f in rec['prim_poses']]);q=np.array([f[idx][1] for f in rec['prim_poses']])
        T=np.tile(np.eye(4),(len(p),1,1));T[:,:3,3]=p
        T[:,:3,:3]=Rotation.from_quat(q[:,[1,2,3,0]]).as_matrix()
        return T
    obj=matrices(meta['object_paths'][a.object])
    ee_info=meta['end_effector_paths'][a.robot];ee=matrices(ee_info['left'])
    offset=np.eye(4);offset[2,3]=ee_info['tcp_offset'] # FR3 convention only
    if a.robot!='franka':raise ValueError('Confirm TCP axis for other embodiments before exporting')
    proprio=log['proprio_data_logger'][a.robot]
    states=np.asarray(proprio['states.joint.position'])
    actions=log['action_data_logger'][a.robot]
    joint_actions=np.asarray(actions['master_actions.joint.position'])
    gripper_open=np.asarray(actions['master_actions.gripper.openness'])
    if not (len(states)==len(obj)==len(joint_actions)==len(gripper_open)):
        raise ValueError('Robot state/action and scene trajectory length mismatch')
    np.savez_compressed(a.output,object_T=obj,ee_T=ee,tcp_T=ee@offset,robot_joint_state=states,
                        robot_joint_action=joint_actions,gripper_open_command=gripper_open,
                        gripper_width=np.asarray(proprio['states.gripper.position']),
                        frame_index=np.arange(len(obj)),dt=meta['physics_dt'])
    print(f'Exported {len(obj)} frames; world frame, meters, 4x4 column-vector transforms')
if __name__=='__main__':main()
