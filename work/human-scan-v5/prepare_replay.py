"""Freeze the accepted robot episode before integrating a new scanned human.

No avatar substitution is performed here. Legacy human contact landmarks are
initialization/reference data, never new-avatar joint-angle targets.
"""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path('/vepfs/public/pengjiaqi/interndata-human-pair')
BASE = ROOT / 'human-scan-v5'
SOURCE = ROOT / 'human-stack-v3/source'
OLD = ROOT / 'human-natural-v4/human-animation.npz'
BASE.mkdir(exist_ok=True)
(BASE / 'source').mkdir(exist_ok=True)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


timing = json.loads((SOURCE / 'contact-schedule.json').read_text())
N, fps = timing['frames'], timing['fps']
tracks = dict(np.load(SOURCE / 'world-tracks.npz', allow_pickle=False))
old = dict(np.load(OLD, allow_pickle=False))
assert N == 1507 and fps == 15
assert np.array_equal(old['source_frame'], np.arange(N))
assert np.allclose(old['video_time_s'], np.arange(N) / fps, atol=1e-12)
for name, values in tracks.items():
    assert np.array_equal(values, old[name]), name
    if name.endswith('_world'):
        assert values.shape == (N, 4, 4)
        assert np.isfinite(values).all()
        R = values[:, :3, :3]
        assert np.max(np.abs(R.transpose(0, 2, 1) @ R - np.eye(3))) < 1e-6
        assert np.max(np.abs(np.linalg.det(R) - 1)) < 1e-6

source_hashes = {}
for path in SOURCE.iterdir():
    if not path.is_file():
        continue
    target = BASE / 'source' / path.name
    source_hashes[path.name] = digest(path)
    if not target.exists() or digest(target) != source_hashes[path.name]:
        shutil.copy2(path, target)
    assert digest(target) == source_hashes[path.name]

probe = json.loads(subprocess.check_output([
    'ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
    '-show_entries', 'stream=nb_read_frames,r_frame_rate,duration,width,height',
    '-of', 'json', str(BASE / 'source/robot-full.mp4')]))['streams'][0]
assert int(probe['nb_read_frames']) == N and probe['r_frame_rate'] == '15/1'

# Evaluate the OLD human rig only to preserve spatial initialization landmarks.
sys.path.insert(0, str(ROOT / 'human41'))
from human_control import Human
h = Human()
h.world = old['world_transform']
global_joints = np.stack([h.fk(local) for local in old['local']])
reference = {
    'source_frame': np.arange(N),
    'video_time_s': np.arange(N) / fps,
    'camera_reference_world_usd': old['camera_world_usd'],
    'wrist_reference_world': old['wrist_targets'],
}
for side in ['L', 'R']:
    reference[side + '_arm_reference_world'] = global_joints[:, [
        h.idx(side + '_' + n) for n in ['Clavicle', 'Upperarm', 'Forearm', 'Hand']]]
    tips = []
    for finger in h.fingers:
        joint = global_joints[:, h.idx(side + '_' + finger + '3')]
        tips.append(joint[:, :3, 3] + joint[:, :3, 1] * h.tip_length[finger])
    reference[side + '_tip_reference_world'] = np.stack(tips, axis=1)

segments = []
for side, label in [('L', 'left'), ('R', 'right')]:
    for event in [timing[label], dict(timing['tray'], object='place_object', release=N-1)]:
        start, stop = event['grasp'], event['release'] + 1
        T = tracks[event['object'] + '_world'][start:stop]
        inv = np.linalg.inv(T)
        points = reference[side + '_tip_reference_world'][start:stop]
        local = np.einsum('nij,nkj->nki', inv[:, :3, :3], points - T[:, None, :3, 3])
        key = side + '_' + event['object'] + '_tip_reference_object'
        reference[key] = local
        segments.append(dict(side=side, object=event['object'], start=start,
                             stop_exclusive=stop, reference_key=key))

np.savez_compressed(BASE / 'contact-initialization.npz', **reference)
report = dict(
    status='source_verified',
    frames=N, fps=fps, video_duration_s=N/fps, last_frame_time_s=(N-1)/fps,
    source_hashes=source_hashes, robot_video_probe=probe,
    legacy_human_animation_sha256=digest(OLD),
    source_arrays_equal_to_accepted_human=True,
    object_trajectory_changes=0, dropped_or_duplicated_frames=0,
    reference_sha256=digest(BASE / 'contact-initialization.npz'),
    contacts=segments,
    conventions='Z-up, meters; column-vector 4x4 poses; USD cameras look along local -Z',
    provenance='InternDataEngine official pipeline with documented task-local stable_place fixes',
    new_avatar_requirements=[
        'Inspect actual mesh, textures, rig, units, skin weights and source license',
        'Refit surface contacts for the new hand shape; old fingertips are only initialization',
        'Solve anatomy and temporal continuity using new bone lengths, never robot joint angles',
        'Keep all source object poses, frame indices and task events unchanged',
        'Fit ego camera to new eyes and verify continuity; render close frontal observer too',
        'Validate full 1507-frame videos and source hashes before delivery',
    ],
    limitation='No new high-resolution avatar loaded, retargeted or rendered yet',
)
(BASE / 'replay-contract.json').write_text(json.dumps(report, indent=2))
print(json.dumps({k: report[k] for k in ['status', 'frames', 'fps', 'video_duration_s',
      'source_arrays_equal_to_accepted_human', 'object_trajectory_changes']}, indent=2))
