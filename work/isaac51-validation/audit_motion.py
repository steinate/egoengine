"""Read-only audit of motion inputs; does not change or simulate trajectories."""
import json
from pathlib import Path
import numpy as np

root = Path('/vepfs/public/pengjiaqi/interndata-human-pair')
base = root / 'validation51'
motion = np.load(root / 'gaussian-ego/output/motion.npz')
tracks = np.load(root / 'outputs41/human-ego/world-tracks.npz')
ids = np.arange(0, 91, 3)
joints = motion['joints'][ids]
arm = motion['arm'][ids]
# Pairwise distances are invariant to rigid wrist translation/rotation.
distances = np.linalg.norm(joints[:, :, None] - joints[:, None, :], axis=-1)
report = {
    'source_frames': (ids + 420).tolist(),
    'joint_array_shape': list(joints.shape),
    'max_joint_pair_distance_range_m': float(np.ptp(distances, axis=0).max()),
    'wrist_max_displacement_from_first_m': float(np.linalg.norm(joints[:, 0] - joints[0, 0], axis=-1).max()),
    'arm_landmark_max_displacement_from_first_m': {
        name: float(np.linalg.norm(arm[:, j] - arm[0, j], axis=-1).max())
        for j, name in enumerate(['shoulder', 'elbow', 'wrist'])
    },
    'objects': {},
    'note': 'Input-motion audit only, not a new physics/contact-success test. Fixed shoulder is expected for this seated-camera prototype.'
}
for name in ['place_object', 'pick_object_left1', 'pick_object_right1']:
    xyz = tracks[name + '_world'][420:511, :3, 3]
    report['objects'][name] = {
        'world_z_min_m': float(xyz[:, 2].min()),
        'world_z_max_m': float(xyz[:, 2].max()),
        'world_z_final_minus_initial_m': float(xyz[-1, 2] - xyz[0, 2]),
    }
(base / 'delivery').mkdir(exist_ok=True)
(base / 'delivery/motion-audit.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
