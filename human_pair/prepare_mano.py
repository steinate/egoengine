"""Create a mesh cache from explicit MANO poses and world-space wrist targets.

This does not infer grasps. Input NPZ: wrist_T[T,4,4], hand_pose[T,45],
betas[10], shoulder[3], pole[3], upper_length scalar, fore_length scalar.
Requires a user-provided licensed MANO_RIGHT.pkl. All lengths in meters.
"""
import argparse
from pathlib import Path
import numpy as np
from .geometry import center_mano_vertices, two_bone_ik


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--model',required=True)
    ap.add_argument('--input',required=True)
    ap.add_argument('--output',required=True)
    args=ap.parse_args()
    import torch, smplx
    if not Path(args.model).is_file():
        raise FileNotFoundError('Provide your licensed MANO_RIGHT.pkl path')
    d=np.load(args.input,allow_pickle=False)
    T=d['wrist_T']; pose=d['hand_pose']; n=len(T)
    if T.shape!=(n,4,4) or pose.shape!=(n,45):raise ValueError('Invalid pose shapes')
    model=smplx.MANO(args.model,is_rhand=True,use_pca=False,flat_hand_mean=True,batch_size=1)
    all_v=[]
    for start in range(0,n,128):
        count=min(128,n-start)
        with torch.no_grad():
            result=model(betas=torch.tensor(np.broadcast_to(d['betas'],(count,10)).copy(),dtype=torch.float32),
                hand_pose=torch.tensor(pose[start:start+count],dtype=torch.float32),
                global_orient=torch.zeros(count,3),transl=torch.zeros(count,3))
        all_v.append(center_mano_vertices(result.vertices.numpy(),result.joints.numpy(),T[start:start+count]))
    s=np.broadcast_to(d['shoulder'],(n,3)); pole=np.broadcast_to(d['pole'],(n,3))
    elbows=np.stack([two_bone_ik(s[t],T[t,:3,3],float(d['upper_length']),float(d['fore_length']),pole[t]) for t in range(n)])
    vertices=np.concatenate(all_v)
    if np.max(np.linalg.norm(vertices-T[:,None,:3,3],axis=-1)) > .5:
        raise ValueError('Hand exceeds 0.5 m from wrist: check model units')
    np.savez_compressed(args.output,vertices=vertices.astype(np.float32),faces=model.faces,
        shoulder=s,elbow=elbows,wrist=T[:,:3,3],wrist_T=T,hand_pose=pose,betas=d['betas'])
    print(f'Saved {n} frames to {args.output}; grasp/collision quality still requires validation')

if __name__=='__main__':main()
