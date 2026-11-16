import sys, json, hashlib, csv
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation

ROOT = Path("/vepfs/public/pengjiaqi/interndata-human-pair")
BASE = ROOT / "paired-human-ego"
OUT = BASE / "delivery"
OUT.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT / "human41"))
from human_control import Human

h = Human()
a = np.load(BASE / "human-animation.npz")
h.world = a["world_transform"]
src = ROOT / "outputs41/human-ego/world-tracks.npz"
original = np.load(src)
objects = ["place_object", "pick_object_left1", "pick_object_right1"]
N = len(a["source_frame"])
assert N == 844
same = {n: bool(np.array_equal(a[n + "_world"], original[n + "_world"])) for n in objects}
assert all(same.values())
g = np.array([h.fk(p) for p in a["local"]])
wrist = g[:, [h.idx("L_Hand"), h.idx("R_Hand")]]
target = a["wrist_targets"]
poserr = np.linalg.norm(wrist[:, :, :3, 3] - target[:, :, :3, 3], axis=-1)
roterr = Rotation.from_matrix(
    (np.swapaxes(wrist[:, :, :3, :3], -1, -2) @ target[:, :, :3, :3]).reshape(-1, 3, 3)
).magnitude()
assert poserr.max() < 1e-6 and roterr.max() < 1e-6
lengtherrors = []
for side in ["L", "R"]:
    for n1, n2 in [("Upperarm", "Forearm"), ("Forearm", "Hand")]:
        j1, j2 = h.idx(side + "_" + n1), h.idx(side + "_" + n2)
        lens = np.linalg.norm(g[:, j2, :3, 3] - g[:, j1, :3, 3], axis=1)
        lengtherrors.append(float(np.ptp(lens)))
contacterrors = {}
for name, side, obj, start, end in [
    ("left_cube", 0, "pick_object_left1", 135, 291),
    ("right_cube", 1, "pick_object_right1", 445, 615),
    ("left_tray", 0, "place_object", 708, 843),
    ("right_tray", 1, "place_object", 708, 843),
]:
    local = np.linalg.inv(a[obj + "_world"][start : end + 1]) @ wrist[start : end + 1, side]
    contacterrors[name] = float(np.max(np.abs(local - local[0])))
    assert contacterrors[name] < 1e-6
mid = (g[:, h.idx("L_Eye"), :3, 3] + g[:, h.idx("R_Eye"), :3, 3]) / 2
eyedistance = np.linalg.norm(a["camera_world_usd"][:, :3, 3] - mid, axis=1)
assert np.max(np.abs(eyedistance - 0.018)) < 1e-6
export = {
    "source_frame": a["source_frame"],
    "video_time_s": a["video_time_s"],
    "left_hand_world": wrist[:, 0],
    "right_hand_world": wrist[:, 1],
    "camera_world_usd": a["camera_world_usd"],
    "camera_world_opencv": a["camera_world_usd"] @ np.diag([1, -1, -1, 1]),
    "eye_midpoint_world": mid,
    "left_elbow_world": g[:, h.idx("L_Forearm"), :3, 3],
    "right_elbow_world": g[:, h.idx("R_Forearm"), :3, 3],
}
for n in objects:
    export[n + "_world"] = a[n + "_world"]
np.savez_compressed(OUT / "paired-world-trajectories.npz", **export)
with open(OUT / "object-trajectories.csv", "w") as f:
    writer = csv.writer(f)
    writer.writerow(
        ["source_frame", "video_time_s", "object", "x_m", "y_m", "z_m", "qw", "qx", "qy", "qz"]
    )
    for i in range(N):
        for n in objects:
            M = a[n + "_world"][i]
            q = Rotation.from_matrix(M[:3, :3]).as_quat()[[3, 0, 1, 2]]
            writer.writerow([i, i / 15, n, *M[:3, 3], *q])
with open(OUT / "frame-alignment.csv", "w") as f:
    writer = csv.writer(f)
    writer.writerow(["human_frame", "official_robot_frame", "video_time_s", "phase"])
    for i in range(N):
        phase = (
            "left_reach"
            if i < 135
            else "left_carry"
            if i <= 291
            else "left_release_right_reach"
            if i < 445
            else "right_carry"
            if i <= 615
            else "right_release_tray_reach"
            if i < 708
            else "tray_contact_and_lift"
        )
        writer.writerow([i, i, i / 15, phase])
report = {
    "source": "Official InternDataEngine dual-arm stack_cubes_lift/lr.yaml, seed42",
    "upstream_commit": "2a0a21f2c836df97c925729084e13d68950b4deb",
    "source_world_tracks_sha256": hashlib.sha256(src.read_bytes()).hexdigest(),
    "frames": N,
    "fps": 15,
    "duration_s": N / 15,
    "objects_bitwise_equal_to_source": same,
    "max_fk_wrist_position_error_m": float(poserr.max()),
    "max_fk_wrist_rotation_error_rad": float(roterr.max()),
    "max_arm_bone_length_variation_m": max(lengtherrors),
    "object_relative_hand_lock_max_matrix_error": contacterrors,
    "eye_camera_offset_m": [float(eyedistance.min()), float(eyedistance.max())],
    "head_visibility": "Own face/head/hat hidden only for first-person view; observer retains complete avatar",
    "timestamp_note": "video_time_s is exact frame/fps alignment. Raw export has frame indices, no recovered wall-clock timestamps. Internal nominal_sim_time_s is an estimate using configured physics_dt, not a measured timestamp.",
    "method": "Kinematic human visual retargeting of the official robot episode, not a new human physics task",
    "limitations": [
        "Hand contacts use skeleton/capsule fitting; full mesh collision and human motion naturalness are not certified.",
        "Reallusion Worker evaluation asset is not licensed here for training or redistribution. No proprietary avatar geometry or texture is included.",
    ],
}
(OUT / "pair-verification.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
