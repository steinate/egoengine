"""Check rendered camera stability, native eye attachment, and unchanged task states."""

import argparse, json
from pathlib import Path
import numpy as np

p = argparse.ArgumentParser()
p.add_argument("episode", type=Path)
a = p.parse_args()
ep = a.episode
s = np.load(ep / "source/world-tracks.npz")
d = np.load(ep / "human/human-animation.npz")
r = json.loads((ep / "human/render/verification.json").read_text())
retarget = json.loads((ep / "human/retarget-report.json").read_text())
C = d["camera_world_usd"]
front = np.asarray(r["front_camera_world"])
names = [str(n).split("/")[-1] for n in d["names"]]
eye_ids = [names.index("L_Eye"), names.index("R_Eye")]
attachment = []
for i in range(len(C)):
    g = d["local"][i].copy()
    for j, parent in enumerate(d["parents"]):
        g[j] = (d["world_transform"] if parent < 0 else g[parent]) @ g[j]
    actual = g[eye_ids, :3, 3].mean(0) - C[i, :3, 2] * 0.018
    attachment.append(float(np.linalg.norm(actual - C[i, :3, 3])))
metrics = dict(
    max_camera_change=float(np.abs(C - C[0]).max()),
    max_native_eye_attachment_error_m=max(attachment),
    max_ego_roll_component=float(np.abs(C[:, 2, 0]).max()),
    front_camera_table_edge_alignment=float(abs(front[0, 0])),
    max_ego_table_edge_misalignment=float(np.abs(C[:, 1:3, 0]).max()),
)
checks = dict(
    camera_fixed=metrics["max_camera_change"] < 1e-7,
    eye_attached=metrics["max_native_eye_attachment_error_m"] < 1e-7,
    no_ego_roll=metrics["max_ego_roll_component"] < 1e-7,
    table_aligned_ego=metrics["max_ego_table_edge_misalignment"] < 1e-7,
    front_table_aligned=abs(metrics["front_camera_table_edge_alignment"] - 1) < 1e-7,
    all_source_arrays_identical=all(np.array_equal(s[k], d[k]) for k in s.files),
    render_used_same_camera=np.allclose(C[0], r["ego_camera_world"], atol=1e-8),
)
if "head_reference_world" in retarget:
    from scipy.spatial.transform import Rotation

    reference = s["camera_world"][0]
    metrics.update(
        body_rotation_error=float(
            np.max(np.abs(d["world_transform"][:3, :3] - np.diag([-1.0, -1.0, 1.0])))
        ),
        head_reference_distance_m=float(np.linalg.norm(C[0, :3, 3] - reference[:3, 3])),
        head_reference_rotation_error_deg=float(
            np.rad2deg(Rotation.from_matrix(reference[:3, :3].T @ C[0, :3, :3]).magnitude())
        ),
    )
    checks.update(
        body_upright_and_table_facing=metrics["body_rotation_error"] < 1e-7,
        # A 20 cm envelope permits the native arm to close the microwave
        # without sacrificing the separate 1 cm fingertip target gate.
        near_robot_head_position=metrics["head_reference_distance_m"] < 0.20,
        near_robot_head_orientation=metrics["head_reference_rotation_error_deg"] < 3,
        robot_head_lens_match=abs(
            r["ego_focal_length_mm"] - retarget["gaze"]["robot_reference_focal_equivalent_mm"]
        )
        < 1e-6,
    )
report = dict(
    passed=all(checks.values()),
    checks={k: bool(v) for k, v in checks.items()},
    metrics=metrics,
    note="Fixed native eye camera; upright table-facing torso and robot head-camera reference checks when present; visual review still required.",
)
(ep / "human/camera-verification.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
assert report["passed"]
