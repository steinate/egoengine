"""Compensate residual wrist orientation error while retaining object-local fingertip targets."""

import argparse, json, sys
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

p = argparse.ArgumentParser()
p.add_argument("root", type=Path)
p.add_argument("episode", type=Path)
p.add_argument("--folder", default="human")
a = p.parse_args()
sys.path.insert(0, str(a.root / "human41"))
from human_control import Human
from worker import fingers, tip_local, FINGER_LOW, FINGER_HIGH

h = Human()
assert Path(a.folder).name == a.folder
folder = a.episode / a.folder
d = dict(np.load(folder / "human-animation.npz"))
r = json.loads((folder / "retarget-report.json").read_text())
h.world = d["world_transform"]
before = []
after = []
for side, c in r["contacts"].items():
    si = 0 if side == "L" else 1
    previous = None
    for i in range(c["grasp"], c["release"] + 1):
        nominal = d["finger_q"][i, si].copy()
        H = d["wrist_targets"][i, si]
        actual = h.fk(d["local"][i])[h.idx(side + "_Hand")]
        goal = tip_local(h, side, nominal) @ H[:3, :3].T + H[:3, 3]

        def residual(f):
            tips = tip_local(h, side, f) @ actual[:3, :3].T + actual[:3, 3]
            return np.r_[
                (tips - goal).ravel() * 300,
                (f - nominal) * 0.3,
                (f - (nominal if previous is None else previous)) * 0.4,
            ]

        initial = nominal if previous is None else previous
        initial_error = np.linalg.norm(
            tip_local(h, side, nominal) @ actual[:3, :3].T + actual[:3, 3] - goal, axis=1
        ).max()
        before.append(initial_error)
        if initial_error > 0.002:
            fit = least_squares(
                residual,
                np.clip(initial, FINGER_LOW + 1e-6, FINGER_HIGH - 1e-6),
                bounds=(FINGER_LOW, FINGER_HIGH),
                max_nfev=35,
            )
            f = fit.x
        else:
            f = nominal
        d["local"][i] = fingers(h, side, f, d["local"][i])
        d["finger_q"][i, si] = f
        previous = f
        after.append(
            float(
                np.linalg.norm(
                    tip_local(h, side, f) @ actual[:3, :3].T + actual[:3, 3] - goal, axis=1
                ).max()
            )
        )
assert max(after) < 0.01, ("Finger target error", max(after))
np.savez_compressed(folder / "human-animation.npz", **d)
r["finger_contact_refinement"] = {
    "before_max_target_error_m": float(max(before)),
    "after_max_target_error_m": float(max(after)),
    "contact_frames": len(after),
}
(folder / "retarget-report.json").write_text(json.dumps(r, indent=2))
print("CONTACT_REFINEMENT_DONE", r["finger_contact_refinement"])
assert max(after) < 0.01
