"""Validate source chronology, physical outcome, and full video before human replay."""

import argparse, json, subprocess
from pathlib import Path
import numpy as np

p = argparse.ArgumentParser()
p.add_argument("episode", type=Path)
a = p.parse_args()
ep = a.episode
r = json.loads((ep / "result.json").read_text())
d = np.load(ep / "source/world-tracks.npz")
m = json.loads((ep / "source/scene-meta.json").read_text())
events = json.loads((ep / "source/events.json").read_text())
prov = json.loads((ep / "task-provenance.json").read_text())
name = prov["object"]
T = d[name + "_world"]
xyz = T[:, :3, 3]
N = len(xyz)
checks = {
    "official_success": r["official_success"],
    "one_physics_tick_per_frame": bool(np.all(np.diff(d["physics_step"]) == 1)),
    "continuous_30hz": bool(np.allclose(np.diff(d["time_s"]), 1 / 30, atol=1e-7)),
    "finite_states": bool(all(np.all(np.isfinite(d[k])) for k in d.files)),
}
metrics = {
    "frames": N,
    "duration_s": float(d["time_s"][-1] + 1 / 30),
    "max_lift_m": float(xyz[:, 2].max() - xyz[0, 2]),
    "end_drift_m": float(np.max(np.linalg.norm(xyz[-30:] - xyz[-1], axis=1))),
}
phase = [z for e in events for z in e["phase"]]
if ep.parent.name == "close_microwave":
    angles = d[name + "_joints"][:, 0]
    metrics.update(initial_angle_rad=float(angles[0]), final_angle_rad=float(angles[-1]))
    checks.update(
        door_closed=bool(abs(angles[-1]) < 0.08),
        door_moved=bool(angles[0] - angles[-1] > 0.3),
        base_stationary=bool(np.max(np.linalg.norm(xyz - xyz[0], axis=1)) < 0.01),
    )
else:
    checks.update(
        object_lifted=metrics["max_lift_m"] > 0.05,
        stable_final_position=metrics["end_drift_m"] < 0.008,
    )
    if ep.parent.name == "hang_cup":
        from pxr import Usd
        from geometry import object_meshes, bounds

        stage = Usd.Stage.Open(str(ep / "source/scene.usdc"))
        cup = object_meshes(stage, m, m["objects"][name]["prim_path"])
        rack = object_meshes(stage, m, m["objects"]["oo3d_object2"]["prim_path"])
        supported = []
        for frame in range(N - 30, N):
            lo, hi = bounds(cup, d["prim_world"][frame])
            rlo, rhi = bounds(rack, d["prim_world"][frame])
            supported.append(
                bool(
                    lo[2] > rlo[2] + 0.05 and np.all(np.minimum(hi, rhi) - np.maximum(lo, rlo) > 0)
                )
            )
        checks.pop("stable_final_position")
        checks["cup_remains_in_rack_support_region"] = all(supported)
        metrics["supported_tail_frames"] = sum(supported)
        metrics["end_motion_note"] = (
            "A hanging cup may swing; test persistent support-region overlap and elevated bottom, not zero motion."
        )
        checks["cup_remains_elevated"] = bool(xyz[-1, 2] > xyz[0, 2] + 0.04)
    if ep.parent.name == "handover":
        checks["both_hands_grasped"] = all(
            any(z["side"] == s and z["command"] == "attach_obj" for z in phase)
            for s in ["left", "right"]
        )
        checks["both_hands_released"] = all(
            any(
                z["side"] == s and z["command"] == "open_gripper" and z["skill"] != "Pick"
                for z in phase
            )
            for s in ["left", "right"]
        )
        plate = d["place_object_world"][-1, :3, 3]
        metrics["final_plate_xy_distance_m"] = float(np.linalg.norm(xyz[-1, :2] - plate[:2]))
        checks["within_plate_region"] = metrics["final_plate_xy_distance_m"] < 0.15
probe = json.loads(
    subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-count_frames",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=nb_read_frames,duration",
            "-of",
            "json",
            str(ep / "source/robot-raw.mp4"),
        ]
    )
)["streams"][0]
checks["all_video_frames"] = int(probe["nb_read_frames"]) == N
checks["video_duration"] = abs(float(probe["duration"]) - N / 30) < 1 / 30
out = dict(passed=all(checks.values()), checks=checks, metrics=metrics, video=probe)
(ep / "source-validation.json").write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=2))
assert out["passed"], out
