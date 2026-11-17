"""Numerical acceptance gate for task-aligned native-human replay."""

import argparse, hashlib, json
from pathlib import Path
import numpy as np

p = argparse.ArgumentParser()
p.add_argument("episode", type=Path)
p.add_argument("--folder", default="human")
a = p.parse_args()
ep = a.episode
assert Path(a.folder).name == a.folder
folder = ep / a.folder
s = np.load(ep / "source/world-tracks.npz")
d = np.load(folder / "human-animation.npz")
r = json.loads((folder / "retarget-report.json").read_text())
checks = {
    "source_hash": r["source_sha256"]
    == hashlib.sha256((ep / "source/world-tracks.npz").read_bytes()).hexdigest(),
    "all_source_states_bitwise_unchanged": all(np.array_equal(s[k], d[k]) for k in s.files),
    "all_frames_present": np.array_equal(d["source_frame"], np.arange(len(s["time_s"]))),
    "time_axis_unchanged": np.array_equal(d["video_time_s"], s["time_s"]),
}
metrics = {
    "max_wrist_error_m": float(d["ik_errors"][:, :, 0].max()),
    "max_wrist_angle_error_deg": float(np.rad2deg(d["ik_errors"][:, :, 1].max())),
    "max_native_arm_joint_step_deg": float(np.rad2deg(np.abs(np.diff(d["arm_q"], axis=0)).max())),
    "max_foot_drift_m": float(np.linalg.norm(d["feet"] - d["feet"][0], axis=-1).max()),
    "max_fitted_fingertip_error_m": max(c["fit_tip_error_m"] for c in r["contacts"].values()),
    "max_refined_fingertip_target_error_m": r["finger_contact_refinement"][
        "after_max_target_error_m"
    ],
}
checks.update(
    wrist_position=metrics["max_wrist_error_m"] < 0.01,
    wrist_orientation=metrics["max_wrist_angle_error_deg"] < 15,
    no_large_joint_jump=metrics["max_native_arm_joint_step_deg"] < 15,
    feet_fixed=metrics["max_foot_drift_m"] < 1e-7,
    fingertip_fit=metrics["max_fitted_fingertip_error_m"] < 0.02,
    refined_fingertip_target=metrics["max_refined_fingertip_target_error_m"] < 0.01,
)
report = dict(
    passed=all(checks.values()),
    checks=checks,
    metrics=metrics,
    note="Numerical gate only; rendered grasp/occlusion/whole-body review still required.",
)
(folder / "validation.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
assert report["passed"], report
