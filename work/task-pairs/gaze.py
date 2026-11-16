"""Align native neck/head and the eye camera with the manipulation workspace."""

import argparse, json, sys
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation

p = argparse.ArgumentParser()
p.add_argument("root", type=Path)
p.add_argument("episode", type=Path)
p.add_argument("--follow-object", action="store_true")
a = p.parse_args()
sys.path.insert(0, str(a.root / "human41"))
from human_control import Human

h = Human()
folder = a.episode / "human"
d = dict(np.load(folder / "human-animation.npz"))
r = json.loads((folder / "retarget-report.json").read_text())
h.world = d["world_transform"]
sys.path.insert(0, str(Path(__file__).parent))
from worker import tip_local

contact_points = []
for side, c in r["contacts"].items():
    si = 0 if side == "L" else 1
    for i in range(c["grasp"], c["release"] + 1, 10):
        H = d["wrist_targets"][i, si]
        tip = tip_local(h, side, d["finger_q"][i, si]).mean(0)
        contact_points.append(H[:3, :3] @ tip + H[:3, 3])
center = np.mean(contact_points, axis=0)
centers = np.tile(center, (len(d["local"]), 1))
if a.follow_object:
    from scipy.ndimage import gaussian_filter1d

    meta = json.loads((a.episode / "source/scene-meta.json").read_text())
    tracks = []
    for side, c in r["contacts"].items():
        si = 0 if side == "L" else 1
        frame = c["grasp"]
        H = h.fk(d["local"][frame])[h.idx(side + "_Hand")]
        point = H[:3, :3] @ tip_local(h, side, d["finger_q"][frame, si]).mean(0) + H[:3, 3]
        M = d["prim_world"][:, meta["prim_paths"].index(c["path"])]
        local_point = np.linalg.inv(M[frame]) @ np.r_[point, 1.0]
        tracks.append((M @ local_point)[:, :3])
    centers = gaussian_filter1d(np.mean(tracks, axis=0), sigma=6, axis=0, mode="nearest")
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
    target = centers[i] - eye
    target /= np.linalg.norm(target)
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
np.savez_compressed(folder / "human-animation.npz", **d)
r["gaze"] = {
    "method": "Native neck/head share gaze rotation 35/65%; camera uses posed eye position and same gaze direction",
    "max_total_rotation_deg": float(np.rad2deg(max(angles))),
    "workspace_center": center.tolist(),
    "follow_object": a.follow_object,
    "head_target_smoothing_seconds": 0.2 if a.follow_object else None,
}
(folder / "retarget-report.json").write_text(json.dumps(r, indent=2))
print("GAZE_DONE", r["gaze"])
