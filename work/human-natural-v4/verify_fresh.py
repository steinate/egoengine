"""Frame/geometry and motion checks for a fresh Worker episode, without old caches."""

import hashlib
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
source_path = B / "source/world-tracks.npz"
source = dict(np.load(source_path))
N = len(source["place_object_world"])
schedule = json.loads((B / "source/contact-schedule.json").read_text())
objects = ["place_object", "pick_object_left1", "pick_object_right1"]
same = {name: bool(np.array_equal(a[name], value)) for name, value in source.items()}
assert all(same.values()), "Source arrays changed"
assert len(a["local"]) == N
assert np.isfinite(a["local"]).all()
h.world = a["world_transform"]
g = np.array([h.fk(p) for p in a["local"]])
wrists = g[:, [h.idx(s + "_Hand") for s in ["L", "R"]]]
errors = np.linalg.norm(wrists[:, :, :3, 3] - a["wrist_targets"][:, :, :3, 3], axis=-1)
torso_ids = [j for j, name in enumerate(h.short) if name in ["Hip", "Waist", "Spine01", "Spine02"]]
assert torso_ids
assert np.allclose(a["local"][:, torso_ids], h.rest[torso_ids], atol=1e-12)
assert np.array_equal(a["hip_lean_rad"], np.zeros(N))
finger_fit = json.loads((B / "finger-contact-refinement.json").read_text())
stats = {}
for si, (side, sign) in enumerate([("L", -1), ("R", 1)]):
    S, E, W = (g[:, h.idx(side + n), :3, 3] for n in ["_Upperarm", "_Forearm", "_Hand"])
    t = schedule["left" if side == "L" else "right"]
    contacts = {}
    for obj, start, end in [
        (t["object"], t["grasp"], t["release"]),
        ("place_object", schedule["tray"]["grasp"], N - 1),
    ]:
        inverse = np.linalg.inv(a[obj + "_world"][start : end + 1])
        tips = []
        for finger in h.fingers:
            j = h.idx(side + "_" + finger + "3")
            point = (
                g[start : end + 1, j, :3, 3] + g[start : end + 1, j, :3, 1] * h.tip_length[finger]
            )
            tips.append(np.einsum("nij,nj->ni", inverse[:, :3, :3], point) + inverse[:, :3, 3])
        tips = np.stack(tips, axis=1)
        contacts[obj] = float(np.linalg.norm(tips - tips[0], axis=-1).max())
    R = wrists[:, si, :3, :3]
    angular_steps = Rotation.from_matrix(np.swapaxes(R[:-1], 1, 2) @ R[1:]).as_rotvec()
    feet = g[:, h.idx(side + "_Foot"), :3, 3]
    stats[side] = {
        "max_elbow_inward_m": float(np.maximum(sign * ((S - E) @ (-h.world[:3, 0])), 0).max()),
        "max_elbow_second_difference_m": float(np.linalg.norm(np.diff(E, 2, axis=0), axis=1).max()),
        "max_wrist_angular_step_deg": float(
            np.rad2deg(np.linalg.norm(angular_steps, axis=1).max())
        ),
        "max_wrist_angular_second_difference_deg": float(
            np.rad2deg(np.linalg.norm(np.diff(angular_steps, axis=0), axis=1).max())
        ),
        "max_foot_drift_m": float(np.linalg.norm(feet - feet[0], axis=1).max()),
        "max_bone_length_variation_m": float(
            max(np.ptp(np.linalg.norm(E - S, axis=1)), np.ptp(np.linalg.norm(W - E, axis=1)))
        ),
        "fingertip_object_relative_drift_m": contacts,
    }

# Anatomical image-right and one fixed gaze fitted to the full immutable episode.
C = a["camera_world_usd"].copy()
z = C[:, :3, 2]
x = np.tile([1.0, 0, 0], (N, 1))
x -= z * np.sum(x * z, axis=1)[:, None]
x /= np.linalg.norm(x, axis=1)[:, None]
C[:, :3, :3] = np.stack([x, np.cross(z, x), z], axis=-1)
camera_points = []
for name in objects:
    v = source[name + "_mesh_vertices"]
    lo, hi = v.min(0), v.max(0)
    corners = np.array(
        [[x, y, z, 1] for x in [lo[0], hi[0]] for y in [lo[1], hi[1]] for z in [lo[2], hi[2]]]
    )
    points = np.einsum("nij,kj->nki", np.linalg.inv(C) @ source[name + "_world"], corners)
    camera_points.append(points[:, :, :3].reshape(-1, 3))
camera_points = np.concatenate(camera_points)
best = None
for angle in np.linspace(-30, 30, 481):
    adjustment = Rotation.from_rotvec([np.deg2rad(angle), 0, 0]).as_matrix()
    points = camera_points @ adjustment
    depth = -points[:, 2]
    if depth.min() < 0.045:
        continue
    uv = points[:, :2] / depth[:, None] * [1280 * 17 / 36, -1280 * 17 / 36] + [640, 360]
    margin = float(min(uv.min(), (np.array([1280, 720]) - uv).min()))
    if best is None or margin > best[0]:
        best = margin, angle, adjustment
assert best is not None
C[:, :3, :3] = C[:, :3, :3] @ best[2]
a["camera_world_usd"] = C
report = {
    "frames": N,
    "fps": 15,
    "duration_s": N / 15,
    "asset": "Original Reallusion Worker with native skeleton, mesh and textures",
    "source_arrays_bitwise_equal": same,
    "source_world_tracks_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
    "max_wrist_target_position_error_m": float(errors.max()),
    "motion": stats,
    "torso": "Fixed native upright standing pose; no forward bend",
    "root_world_transform": h.world.tolist(),
    "finger_contact_fit": finger_fit,
    "ego_object_image_margin_px": best[0],
    "ego_camera_pitch_adjustment_deg": float(best[1]),
    "ego_focal_length_mm": 17,
    "physics": "Visual retargeting of the verified robot rollout; immutable object replay, not a new human dynamics rollout",
    "robot_stack_validation": json.loads((B / "source/robot-stack-validation.json").read_text()),
}
failures = []
if errors.max() >= 0.003:
    failures.append("wrist target residual >= 3 mm")
if best[0] < 16:
    failures.append("ego framing margin < 16 px")
for side, st in stats.items():
    if st["max_elbow_inward_m"] > 0.002:
        failures.append(side + " inward elbow > 2 mm")
    if st["max_foot_drift_m"] > 1e-6 or st["max_bone_length_variation_m"] > 1e-6:
        failures.append(side + " changed foot position or bone length")
    if st["max_wrist_angular_step_deg"] > 8:
        failures.append(side + " wrist rotation step > 8 degrees")
    if max(st["fingertip_object_relative_drift_m"].values()) > 0.005:
        failures.append(side + " fingertip relative drift > 5 mm")
for name, value in finger_fit.items():
    if isinstance(value, dict) and value["max_fingertip_target_error_m"] > 0.003:
        failures.append(name + " fingertip target error > 3 mm")
if finger_fit["max_finger_parameter_step_deg"] > 7:
    failures.append("finger parameter step > 7 degrees")
report["failures"] = failures
report["passed"] = not failures
(B / "fresh-verification.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2), flush=True)
assert not failures, failures
np.savez_compressed(B / "human-animation.npz", **a)
report["source_animation_sha256"] = hashlib.sha256(
    (B / "human-animation.npz").read_bytes()
).hexdigest()
D = B / "delivery"
D.mkdir(exist_ok=True)
(D / "ik-and-pair-verification.json").write_text(json.dumps(report, indent=2))
np.savez_compressed(
    D / "paired-world-trajectories.npz",
    **source,
    left_hand_world=wrists[:, 0],
    right_hand_world=wrists[:, 1],
    camera_world_usd=C,
)
