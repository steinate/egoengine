"""Aim the native head downward in world space without changing arm/contact poses."""

import json
from pathlib import Path
import sys
import numpy as np
from scipy.spatial.transform import Rotation

B = Path(__file__).resolve().parent
sys.path.insert(0, str(B.parent / "human41"))
from human_control import Human

h = Human()
a = dict(np.load(B / "human-animation.npz"))
h.world = a["world_transform"]
reference = h.fk(h.rest)
right = -h.world[:3, 0]
hands = [h.idx("L_Hand"), h.idx("R_Hand")]
errors = []
for i, p in enumerate(a["local"]):
    previous_hands = h.fk(p)[hands].copy()
    for name, pitch in [("NeckTwist01", -0.25), ("Head", -0.55)]:
        j = h.idx(name)
        g = h.fk(p)
        desired = Rotation.from_rotvec(right * pitch).as_matrix() @ reference[j, :3, :3]
        p[j, :3, :3] = g[h.parents[j], :3, :3].T @ desired
    g = h.fk(p)
    errors.append(float(np.max(np.abs(g[hands] - previous_hands))))
    eye = g[[h.idx("L_Eye"), h.idx("R_Eye")], :3, 3].mean(0)
    a["camera_world_usd"][i, :3, 3] = eye - 0.018 * a["camera_world_usd"][i, :3, 2]
assert max(errors) == 0
np.savez_compressed(B / "human-animation.npz", **a)
report = {
    "max_hand_transform_change": max(errors),
    "head_pitch_degrees": -31.51267873219528,
    "method": "World-space rotation about anatomical right; native local bone axes are not assumed",
}
(B / "head-gaze-verification.json").write_text(json.dumps(report, indent=2))
print("HEAD_GAZE_FIXED", report, flush=True)
