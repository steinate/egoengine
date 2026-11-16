"""Read-only export of official dual manipulation LMDB outputs."""
import argparse, csv, hashlib, json, pickle
from pathlib import Path
import imageio.v2 as imageio
import lmdb
import numpy as np

p=argparse.ArgumentParser()
p.add_argument('episode'); p.add_argument('output'); p.add_argument('task_config')
a=p.parse_args(); episode=Path(a.episode); out=Path(a.output); out.mkdir(parents=True,exist_ok=True)
env=lmdb.open(str(episode/'lmdb'),readonly=True,lock=False)
arrays={}; objects={}; arms={}; cameras={}
with env.begin() as tx:
    keys=[k.decode() for k,_ in tx.cursor()]
    def get(key): return np.asarray(pickle.loads(tx.get(key.encode())))
    object_names=sorted(k[:-12] for k in keys if k.endswith('/translation'))
    for name in object_names:
        xyz=get(name+'/translation'); quat=get(name+'/orientation'); scale=get(name+'/scale')
        arrays[name+'__translation_local_m']=xyz
        arrays[name+'__orientation_wxyz']=quat
        arrays[name+'__scale']=scale
        objects[name]={'frames':len(xyz),'initial_position_m':xyz[0].tolist(),
            'final_position_m':xyz[-1].tolist(),'max_lift_m':float(xyz[:,2].max()-xyz[0,2]),
            'final_lift_m':float(xyz[-1,2]-xyz[0,2]),
            'max_displacement_m':float(np.linalg.norm(xyz-xyz[0],axis=1).max()),
            'finite':bool(np.isfinite(xyz).all() and np.isfinite(quat).all()),
            'max_quaternion_norm_error':float(np.max(np.abs(np.linalg.norm(quat,axis=1)-1)))}
        with (out/(name+'-trajectory.csv')).open('w') as f:
            writer=csv.writer(f);writer.writerow(['video_frame','x_local_m','y_local_m','z_local_m','qw','qx','qy','qz'])
            writer.writerows((i,*pos,*q) for i,(pos,q) in enumerate(zip(xyz,quat)))
    for arm in ['left','right']:
        q=get(f'states.{arm}_joint.position')
        for prefix in ['states','master_actions']:
            for part in ['joint','gripper']:
                key=f'{prefix}.{arm}_{part}.position';arrays[key]=get(key)
        arms[arm]={'frames':len(q),'joint_motion_rad':np.ptp(q,axis=0).tolist(),'finite':bool(np.isfinite(q).all())}
    for key in ['T_base_ee_fl','T_base_ee_fr','T_world_base','qvel']:
        if key in keys:arrays[key]=get(key)
    for name in ['head','hand_left','hand_right']:
        key='camera2env_pose.'+name
        if key in keys:arrays[key]=get(key)
        reader=imageio.get_reader(episode/f'images.rgb.{name}/demo.mp4')
        meta=reader.get_meta_data();n=reader.count_frames()
        for i in sorted(set(np.linspace(0,n-1,9,dtype=int))):
            imageio.imwrite(out/f'{name}-frame-{i:04d}.jpg',reader.get_data(int(i)))
        cameras[name]={'frames':n,'fps':meta['fps'],'size':list(meta['size'])};reader.close()
    raw_meta=pickle.loads(tx.get(b'json_data'))
    (out/'camera-parameters.json').write_text(json.dumps(raw_meta,indent=2))
n=arms['left']['frames']
arrays['video_frame_index']=np.arange(n)
np.savez_compressed(out/'object-and-robot-tracks.npz',**arrays)
result={'source_episode':str(episode),'task_config':str(a.task_config),
    'task_config_sha256':hashlib.sha256(Path(a.task_config).read_bytes()).hexdigest(),
    'frames':n,'objects':objects,'arms':arms,'cameras':cameras,
    'coordinates':'Original RigidObject.get_local_pose(): parent-local translation in metres, quaternion wxyz. No inferred world conversion.',
    'timing':'Arrays follow official recorded frame order. Video is encoded at 15 FPS; simulation physics_dt=1/30. No fabricated simulation timestamps.',
    'integrity_passed':bool(objects) and all(o['frames']==n and o['finite'] for o in objects.values()) and all(s['frames']==n and s['finite'] for s in arms.values()) and all(c['frames']==n for c in cameras.values())}
(out/'verification.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
assert result['integrity_passed']
