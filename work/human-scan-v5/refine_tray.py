"""Clear thumb/pinky overlap with a box approximation of the tray end walls."""

import numpy as np, json, shutil
from pathlib import Path
from scipy.optimize import least_squares
from hand_model import Hand, smooth

B = Path("/vepfs/public/pengjiaqi/interndata-human-pair/human-scan-v5")
anim = dict(np.load(B / "scan-animation.npz"))
mesh = np.load(B / "scan-mesh.npz")
tracks = np.load(B / "source/world-tracks.npz")
ref = np.load(B / "contact-initialization.npz")
reports = []
boxes = [
    ([0, -0.023, 0], [0.153, 0.004, 0.076]),
    ([0.149, 0, 0], [0.005, 0.027, 0.076]),
    ([-0.149, 0, 0], [0.005, 0.027, 0.076]),
    ([0, 0, 0.072], [0.153, 0.027, 0.005]),
    ([0, 0, -0.072], [0.153, 0.027, 0.005]),
]


def sdf(p):
    distances = []
    for center, half in boxes:
        d = abs(p - center) - half
        distances.append(np.linalg.norm(np.maximum(d, 0), axis=1) + np.minimum(d.max(1), 0))
    return np.min(distances, axis=0)


start, end = 1331, 1506
dimensions = np.array([0, 1, 2, 3, 4, 14, 15, 16])
frames = [start, (start + end) // 2, end]
for side in ["L", "R"]:
    h = Hand(mesh, side)
    W = anim[side + "_wrist_world"]
    q = anim[side + "_q"]
    T = tracks["place_object_world"]

    def points(frame, angles, ids):
        p = h.deform(angles, np.eye(4), ids)
        p = p @ W[frame, :3, :3].T + W[frame, :3, 3]
        return (p - T[frame, :3, 3]) @ T[frame, :3, :3]

    selected = []
    pads = []
    goals = []
    for finger, bones in [(0, [1, 2, 3]), (4, [13, 14, 15])]:
        verts = np.where((h.weights * np.isin(h.ids, bones)).sum(1) > 0.5)[0]
        pp = points(start, q[start], verts)
        selected.extend(verts[np.argsort(sdf(pp))[:1000:3]])
        goal = (ref[side + "_tip_reference_world"][start, finger] - T[start, :3, 3]) @ T[
            start, :3, :3
        ]
        goal[0] = np.sign(goal[0]) * (0.1548 if finger == 0 else 0.1432)
        goal[1:] = np.clip(goal[1:], [-0.022, -0.065], [0.025, 0.065])
        candidate = verts[np.linalg.norm(h.v[verts] - h.landmarks[finger, 3], axis=1) < 0.018]
        pp = points(start, q[start], candidate)
        pad = int(candidate[np.linalg.norm(pp - goal, axis=1).argmin()])
        pads.append(pad)
        goals.append(goal)
        selected.append(pad)
    ids = np.unique(selected)
    padidx = [int(np.where(ids == p)[0][0]) for p in pads]

    def residual(delta):
        result = []
        for frame in frames:
            angles = q[frame].copy()
            angles[dimensions] += delta
            pp = points(frame, angles, ids)
            result.extend(np.maximum(0.0008 - sdf(pp), 0) * 120)
            result.extend(((pp[padidx] - goals) * 200).ravel())
        return np.r_[result, delta * 0.35]

    lo = np.maximum(h.lo[dimensions] - q[start : end + 1, dimensions].min(0), -0.45)
    hi = np.minimum(h.hi[dimensions] - q[start : end + 1, dimensions].max(0), 0.45)
    sol = least_squares(
        residual,
        np.clip(np.zeros(8), lo + 1e-6, hi - 1e-6),
        bounds=(lo + 1e-7, hi - 1e-7),
        max_nfev=100,
        ftol=1e-8,
    )
    before = []
    after = []
    for frame in frames:
        before.append(float(max(0, -sdf(points(frame, q[frame], np.arange(len(h.v)))).min())))
        angles = q[frame].copy()
        angles[dimensions] += sol.x
        after.append(float(max(0, -sdf(points(frame, angles, np.arange(len(h.v)))).min())))
    assert max(after) < max(before), side
    weight = smooth((np.arange(len(q)) - (start - 24)) / 24)
    q[:, dimensions] += weight[:, None] * sol.x
    anim[side + "_q"] = q
    reports.append(
        {
            "side": side,
            "frames": frames,
            "max_mesh_penetration_before_m": before,
            "max_mesh_penetration_after_m": after,
            "delta_rad": sol.x.tolist(),
            "geometry": "Five boxes approximating tray walls and base; not exact triangle/force validation",
        }
    )
np.savez_compressed(B / "scan-animation.npz", **anim)
(B / "tray-contact-report.json").write_text(json.dumps(reports, indent=2))
print(json.dumps(reports, indent=2), flush=True)
