"""Refit the scanned thumb surface, not just an approximate fingertip landmark."""

import numpy as np, json, shutil
from pathlib import Path
from scipy.optimize import least_squares
from hand_model import Hand, smooth

B = Path("/vepfs/public/pengjiaqi/interndata-human-pair/human-scan-v6")
source = B / "scan-animation-before-contact.npz"
if not source.exists():
    shutil.copy2(B / "scan-animation.npz", source)
anim = dict(np.load(source))
mesh = np.load(B / "scan-mesh.npz")
tracks = np.load(B / "source/world-tracks.npz")
timing = json.loads((B / "source/contact-schedule.json").read_text())
reference = np.load(B / "contact-initialization.npz")
reports = []
for s, label in [("L", "left"), ("R", "right")]:
    h = Hand(mesh, s)
    event = timing[label]
    start, end = event["grasp"], event["release"]
    obj = event["object"]
    W = anim[s + "_wrist_world"]
    q = anim[s + "_q"]
    T = tracks[obj + "_world"]
    v = tracks[obj + "_mesh_vertices"]
    half = (v.max(0) - v.min(0)) / 2
    center = (v.max(0) + v.min(0)) / 2

    def object_points(frame, angles, ids):
        points = h.deform(angles, np.eye(4), ids)
        world = points @ W[frame, :3, :3].T + W[frame, :3, 3]
        return (world - T[frame, :3, 3]) @ T[frame, :3, :3]

    def sdf(points):
        d = np.abs(points - center) - half
        return np.linalg.norm(np.maximum(d, 0), axis=1) + np.minimum(d.max(1), 0)

    thumb = np.where((h.weights * ((h.ids >= 1) & (h.ids <= 3))).sum(1) > 0.5)[0]
    rest_points = object_points(start, q[start], thumb)
    near = thumb[np.argsort(sdf(rest_points))[:1800]]
    ids = near[::3]
    goal = (reference[s + "_tip_reference_world"][start, 0] - T[start, :3, 3]) @ T[start, :3, :3]
    axis = np.argmax(abs(goal - center) / half)
    goal = np.clip(goal, center - half + 0.001, center + half - 0.001)
    goal[axis] = center[axis] + np.sign(
        (reference[s + "_tip_reference_world"][start, 0] - T[start, :3, 3]) @ T[start, :3, :3]
    )[axis] * (half[axis] + 0.0008)
    tip_candidates = thumb[np.linalg.norm(h.v[thumb] - h.landmarks[0, 3], axis=1) < 0.017]
    pp = object_points(start, q[start], tip_candidates)
    pad = int(tip_candidates[np.linalg.norm(pp - goal, axis=1).argmin()])
    ids = np.unique(np.r_[ids, pad])
    padidx = int(np.where(ids == pad)[0][0])
    sample_frames = [start, (start + end) // 2, end]

    def residual(delta):
        out = []
        for frame in sample_frames:
            angles = q[frame].copy()
            angles[:5] += delta
            pp = object_points(frame, angles, ids)
            out.extend(np.maximum(0.0008 - sdf(pp), 0) * 100)
            out.extend((pp[padidx] - goal) * 300)
        return np.r_[out, delta * 0.4]

    lo = np.maximum(h.lo[:5] - q[start : end + 1, :5].min(0), -0.35)
    hi = np.minimum(h.hi[:5] - q[start : end + 1, :5].max(0), 0.35)
    result = least_squares(
        residual, np.zeros(5), bounds=(lo + 1e-7, hi - 1e-7), max_nfev=100, ftol=1e-8, xtol=1e-8
    )
    delta = result.x
    old_depth = []
    new_depth = []
    for frame in sample_frames:
        old_depth.append(float(max(0, -sdf(object_points(frame, q[frame], thumb)).min())))
        angles = q[frame].copy()
        angles[:5] += delta
        new_depth.append(float(max(0, -sdf(object_points(frame, angles, thumb)).min())))
    assert max(new_depth) < max(old_depth), s
    frames = np.arange(len(q))
    weight = smooth((frames - (start - 24)) / 24) * (1 - smooth((frames - end) / 24))
    q[:, :5] += weight[:, None] * delta
    anim[s + "_q"] = q
    reports.append(
        {
            "side": s,
            "object": obj,
            "frames": sample_frames,
            "thumb_surface_penetration_before_m": old_depth,
            "thumb_surface_penetration_after_m": new_depth,
            "thumb_delta_rad": delta.tolist(),
            "selected_pad_vertex": pad,
            "method": "Actual DQS thumb mesh samples, box surface contact, smooth 24-frame approach/release blending; object poses and wrist trajectory unchanged",
        }
    )
np.savez_compressed(B / "scan-animation.npz", **anim)
(B / "surface-contact-report.json").write_text(json.dumps(reports, indent=2))
print(json.dumps(reports, indent=2), flush=True)
