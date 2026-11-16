"""Align native neck/head and the eye camera with the manipulation workspace."""

import argparse, json, sys
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation

p = argparse.ArgumentParser()
p.add_argument("root", type=Path)
p.add_argument("episode", type=Path)
p.add_argument("--pitch-deg", type=float, default=35.0)
p.add_argument("--folder", default="human")
p.add_argument("--focal-mm", type=float, default=10.0)
a = p.parse_args()
sys.path.insert(0, str(a.root / "human41"))
from human_control import Human

h = Human()
assert Path(a.folder).name == a.folder
folder = a.episode / a.folder
d = dict(np.load(folder / "human-animation.npz"))
r = json.loads((folder / "retarget-report.json").read_text())
h.world = d["world_transform"]
sys.path.insert(0, str(Path(__file__).parent))
# A stable, table-aligned head-mounted view: no hand/object tracking and no roll.
# World +Y is across the table; X is parallel to its front edge.
pitch = np.deg2rad(a.pitch_deg)
direction = np.array([0.0, np.cos(pitch), -np.sin(pitch)])
forward = -h.world[:3, 1]
neck = h.idx("NeckTwist01")
head = h.idx("Head")
eyes = [h.idx("L_Eye"), h.idx("R_Eye")]
angles = []
for i, p0 in enumerate(d["local"]):
    pose = p0.copy()
    # Idempotent: recompute head and neck from the original upright rest pose.
    for j in [neck, h.idx("NeckTwist02"), head]:
        pose[j] = h.rest[j]
    g = h.fk(pose)
    eye = g[eyes, :3, 3].mean(0)
    target = direction.copy()
    D = Rotation.align_vectors([target], [forward])[0]
    rv = D.as_rotvec()
    rv *= min(1.0, 1.48 / max(np.linalg.norm(rv), 1e-8))
    angles.append(np.linalg.norm(rv))
    for j, fraction in [(neck, 0.35), (head, 0.65)]:
        g = h.fk(pose)
        desired = Rotation.from_rotvec(rv * fraction).as_matrix() @ g[j, :3, :3]
        pose[j, :3, :3] = g[h.parents[j], :3, :3].T @ desired
    g = h.fk(pose)
    direction = Rotation.from_rotvec(rv).apply(forward)
    eye = g[eyes, :3, 3].mean(0) + direction * 0.018
    z = -direction
    x = np.cross([0, 0, 1], z)
    x /= np.linalg.norm(x)
    C = np.eye(4)
    C[:3, :3] = np.stack([x, np.cross(z, x), z], 1)
    C[:3, 3] = eye
    d["local"][i] = pose
    d["camera_world_usd"][i] = C
assert np.max(np.abs(d["camera_world_usd"] - d["camera_world_usd"][0])) < 1e-7, (
    "Fixed head camera moved"
)
np.savez_compressed(folder / "human-animation.npz", **d)
r["gaze"] = {
    "method": "Native neck/head share gaze rotation 35/65%; camera uses posed eye position and same gaze direction",
    "max_total_rotation_deg": float(np.rad2deg(max(angles))),
    "fixed_world_direction": direction.tolist(),
    "pitch_deg": a.pitch_deg,
    "focal_length_mm": a.focal_mm,
    "follow_object": False,
    "camera_policy": "Fixed native eye pose, table-aligned yaw, world-up roll; no trajectory-dependent camera target",
}
(folder / "retarget-report.json").write_text(json.dumps(r, indent=2))
print("GAZE_DONE", r["gaze"])
