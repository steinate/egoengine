"""Compare actual joint motion, elbow clearance, and contact consistency."""

import sys, json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation as R

ROOT = Path("/vepfs/public/pengjiaqi/interndata-human-pair")
BASE = ROOT / "human-natural-v4"
sys.path.insert(0, str(ROOT / "human41"))
from human_control import Human

h = Human()
result = {}
for label, path in [
    ("before", ROOT / "human-stack-v3/human-animation.npz"),
    ("after", BASE / "human-animation.npz"),
]:
    a = np.load(path)
    h.world = a["world_transform"]
    g = np.array([h.fk(p) for p in a["local"]])
    stats = {}
    for si, (side, sign, start, end) in enumerate([("L", -1, 137, 433), ("R", 1, 780, 1044)]):
        S, E = g[:, h.idx(side + "_Upperarm"), :3, 3], g[:, h.idx(side + "_Forearm"), :3, 3]
        acc = np.linalg.norm(np.diff(E, 2, axis=0), axis=1)
        s = {
            "max_elbow_inward_m": float(np.maximum(sign * (S[:, 0] - E[:, 0]), 0).max()),
            "min_elbow_outward_clearance_m": float((sign * (E[:, 0] - S[:, 0])).min()),
            "max_elbow_second_difference_m": float(acc.max()),
            "elbow_second_difference_rms_m": float(np.sqrt(np.mean(acc**2))),
            "mean_abs_wrist_deviation_deg": float(np.abs(np.rad2deg(a["arm_q"][:, si, 7])).mean()),
        }
        for bone in ["Upperarm", "Forearm", "Hand"]:
            M = a["local"][:, h.idx(side + "_" + bone), :3, :3]
            delta = R.from_matrix(np.swapaxes(M[:-1], 1, 2) @ M[1:]).as_rotvec()
            d2 = np.linalg.norm(np.diff(delta, axis=0), axis=1)
            s[bone] = {
                "max_angular_step_degrees": float(np.rad2deg(np.linalg.norm(delta, axis=1).max())),
                "max_angular_second_difference_degrees": float(np.rad2deg(d2.max())),
                "rms_angular_second_difference_degrees": float(np.rad2deg(np.sqrt(np.mean(d2**2)))),
            }
        contact = {}
        for name, st, en in [
            (("pick_object_left1" if side == "L" else "pick_object_right1"), start, end),
            ("place_object", 1331, 1506),
        ]:
            inv = np.linalg.inv(a[name + "_world"][st : en + 1])
            W = inv @ g[st : en + 1, h.idx(side + "_Hand")]
            tips = []
            for finger in h.fingers:
                j = h.idx(side + "_" + finger + "3")
                world_tip = (
                    g[st : en + 1, j, :3, 3] + g[st : en + 1, j, :3, 1] * h.tip_length[finger]
                )
                tips.append(np.einsum("nij,nj->ni", inv[:, :3, :3], world_tip) + inv[:, :3, 3])
            tips = np.stack(tips, axis=1)
            drift = np.linalg.norm(tips - tips[0], axis=-1)
            contact[name] = {
                "max_fingertip_relative_drift_m": float(drift.max()),
                "max_wrist_position_drift_m": float(
                    np.linalg.norm(W[:, :3, 3] - W[0, :3, 3], axis=1).max()
                ),
                "max_target_orientation_error_deg": float(
                    np.rad2deg(a["ik_errors"][st : en + 1, si, 1].max())
                ),
            }
        s["contact"] = contact
        stats[side] = s
    result[label] = stats
src = np.load(ROOT / "human-stack-v3/source/world-tracks.npz")
new = np.load(BASE / "human-animation.npz")
result["source_objects_exact"] = {
    n: bool(np.array_equal(new[n + "_world"], src[n + "_world"]))
    for n in ["place_object", "pick_object_left1", "pick_object_right1"]
}
result["frames"] = len(new["source_frame"])
result["timeline_exact"] = bool(
    np.array_equal(new["source_frame"], np.arange(1507))
    and np.array_equal(new["video_time_s"], np.arange(1507) / 15)
)
(BASE / "motion-comparison.json").write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
