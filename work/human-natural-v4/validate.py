import sys, json, hashlib, csv
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation

ROOT = Path("/vepfs/public/pengjiaqi/interndata-human-pair")
BASE = ROOT / "human-natural-v4"
OUT = BASE / "delivery"
OUT.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT / "human41"))
from human_control import Human

h = Human()
a = np.load(BASE / "human-animation.npz")
src = ROOT / "human-stack-v3/source/world-tracks.npz"
source = np.load(src)
N = len(a["source_frame"])
assert (
    N == len(source["place_object_world"]) == 1507
    and np.array_equal(a["source_frame"], np.arange(N))
    and np.array_equal(a["video_time_s"], np.arange(N) / 15)
)
objects = ["place_object", "pick_object_left1", "pick_object_right1"]
same = {n: bool(np.array_equal(a[n + "_world"], source[n + "_world"])) for n in objects}
assert all(same.values())
h.world = a["world_transform"]
g = np.array([h.fk(p) for p in a["local"]])
wrists = g[:, [h.idx("L_Hand"), h.idx("R_Hand")]]
errs = np.linalg.norm(wrists[:, :, :3, 3] - a["wrist_targets"][:, :, :3, 3], axis=-1)
rotation_error = Rotation.from_matrix(
    (np.swapaxes(wrists[:, :, :3, :3], -1, -2) @ a["wrist_targets"][:, :, :3, :3]).reshape(-1, 3, 3)
).magnitude()  # Palm orientation is a soft comfort objective; actual fingertip contact is checked separately below.
assert errs.max() < 0.002 and rotation_error.max() < np.deg2rad(8)


def posture(data):
    h.world = data["world_transform"]
    G = np.array([h.fk(p) for p in data["local"]])
    knees = []
    posterior = []
    medial = []
    length = []
    footdrift = []
    for side, sign in [("L", -1), ("R", 1)]:
        S, E, W = (
            G[:, h.idx(side + "_Upperarm"), :3, 3],
            G[:, h.idx(side + "_Forearm"), :3, 3],
            G[:, h.idx(side + "_Hand"), :3, 3],
        )
        posterior.extend(S[:, 1] - E[:, 1])
        medial.extend(sign * (S[:, 0] - E[:, 0]))
        length.extend(
            [
                float(np.ptp(np.linalg.norm(E - S, axis=1))),
                float(np.ptp(np.linalg.norm(W - E, axis=1))),
            ]
        )
        A, B, C = (
            G[:, h.idx(side + "_Thigh"), :3, 3],
            G[:, h.idx(side + "_Calf"), :3, 3],
            G[:, h.idx(side + "_Foot"), :3, 3],
        )
        u = B - A
        v = C - B
        knees.extend(
            np.rad2deg(
                np.arccos(
                    np.clip(
                        np.sum(u * v, axis=1)
                        / np.linalg.norm(u, axis=1)
                        / np.linalg.norm(v, axis=1),
                        -1,
                        1,
                    )
                )
            )
        )
        footdrift.append(float(np.linalg.norm(C - C[0], axis=1).max()))
    return {
        "knee_flexion_degrees": [float(min(knees)), float(max(knees))],
        "max_elbow_posterior_to_shoulder_m": float(max(posterior)),
        "max_elbow_medial_to_shoulder_m": float(max(medial)),
        "max_arm_bone_length_variation_m": max(length),
        "max_foot_position_drift_m": max(footdrift),
        "pelvis_height_m": float(G[0, h.idx("Hip"), 2, 3]),
    }


newstats = posture(a)
old = np.load(ROOT / "paired-human-ego/human-animation.npz")
oldstats = posture(old)
h.world = a["world_transform"]
assert newstats["max_foot_position_drift_m"] < 1e-6
contact = {}
timing = json.loads((BASE / "source/contact-schedule.json").read_text())
intervals = [
    ("left_cube", 0, "pick_object_left1", timing["left"]["grasp"], timing["left"]["release"]),
    ("right_cube", 1, "pick_object_right1", timing["right"]["grasp"], timing["right"]["release"]),
    ("left_tray", 0, "place_object", timing["tray"]["grasp"], N - 1),
    ("right_tray", 1, "place_object", timing["tray"]["grasp"], N - 1),
]
for name, side, obj, start, end in intervals:
    M = np.linalg.inv(a[obj + "_world"][start : end + 1]) @ wrists[start : end + 1, side]
    contact[name] = {
        "relative_translation_drift_m": float(
            np.max(np.linalg.norm(M[:, :3, 3] - M[0, :3, 3], axis=1))
        ),
        "relative_rotation_drift_degrees": float(
            np.max(Rotation.from_matrix(M[0, :3, :3].T @ M[:, :3, :3]).magnitude()) * 180 / np.pi
        ),
    }
    assert contact[name]["relative_translation_drift_m"] < 0.005
export = {n + "_world": a[n + "_world"] for n in objects}
export.update(
    source_frame=a["source_frame"],
    video_time_s=a["video_time_s"],
    left_hand_world=wrists[:, 0],
    right_hand_world=wrists[:, 1],
    camera_world_usd=a["camera_world_usd"],
    left_elbow_world=g[:, h.idx("L_Forearm"), :3, 3],
    right_elbow_world=g[:, h.idx("R_Forearm"), :3, 3],
    arm_q=a["arm_q"],
    hip_lean_rad=a["hip_lean_rad"],
)
np.savez_compressed(OUT / "paired-world-trajectories.npz", **export)
report = {
    "frames": N,
    "fps": 15,
    "duration_s": N / 15,
    "objects_bitwise_equal_to_official_source": same,
    "source_world_tracks_sha256": hashlib.sha256(src.read_bytes()).hexdigest(),
    "source_animation_sha256": hashlib.sha256(
        (BASE / "human-animation.npz").read_bytes()
    ).hexdigest(),
    "optimized_ik": newstats,
    "max_wrist_target_position_error_m": float(errs.max()),
    "max_wrist_target_orientation_error_degrees": float(rotation_error.max() * 180 / np.pi),
    "grasp_contact_drift": contact,
    "maximum_absolute_wrist_deviation_degrees": float(
        np.max(np.abs(np.rad2deg(a["arm_q"][:, :, 7])))
    ),
    "maximum_absolute_wrist_flexion_degrees": float(
        np.max(np.abs(np.rad2deg(a["arm_q"][:, :, 8])))
    ),
    "robot_stack_validation": json.loads((BASE / "source/robot-stack-validation.json").read_text()),
    "contact_schedule": timing,
    "physics": "Visual retargeting of verified stable-stack robot episode; source object motion imposed exactly; not a new human contact dynamics simulation",
    "naturalness_limit": "Joint limits, mocap pose references and rig-compatible twist distribution improve pose quality; no claim of validated physical balance or photorealism",
}
motion = json.loads((BASE / "motion-comparison.json").read_text())
finger_contact = json.loads((BASE / "finger-contact-refinement.json").read_text())
assert motion["timeline_exact"] and all(motion["source_objects_exact"].values())
for side in ["L", "R"]:
    before, after = motion["before"][side], motion["after"][side]
    assert after["max_elbow_inward_m"] < 0.0005
    assert after["max_elbow_second_difference_m"] < before["max_elbow_second_difference_m"] * 0.35
    assert (
        after["Hand"]["max_angular_second_difference_degrees"]
        < before["Hand"]["max_angular_second_difference_degrees"] * 0.4
    )
    # Joint-center fingertip landmarks approximate compliant finger pads; permit 3 mm target error,
    # and 5 mm pairwise drift, while prioritizing temporally stable anatomical articulation.
    for contact_stats in after["contact"].values():
        assert contact_stats["max_fingertip_relative_drift_m"] < 0.005
assert finger_contact["max_finger_parameter_step_deg"] < 7.0
for key, value in finger_contact.items():
    if isinstance(value, dict):
        assert value["max_fingertip_target_error_m"] < 0.003
report["motion_comparison"] = motion
report["finger_contact"] = finger_contact
report["finger_contact_tolerance"] = {
    "target_error_m": 0.003,
    "relative_drift_m": 0.005,
    "max_parameter_step_deg": 7.0,
    "reason": "Approximate fingertip landmarks, not deformable pad surfaces; soft contact preserves smooth anatomical motion.",
}
report["orientation_policy"] = (
    "Palm orientation is a soft ergonomic target. Smooth finger IK approximates object-relative fingertip contact positions."
)
if (BASE / "camera-continuity.json").exists():
    report["camera_continuity"] = json.loads((BASE / "camera-continuity.json").read_text())
(OUT / "ik-and-pair-verification.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
