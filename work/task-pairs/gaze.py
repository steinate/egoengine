"""Align native neck/head and the eye camera with the manipulation workspace."""

import argparse, json, sys
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation

p = argparse.ArgumentParser()
p.add_argument("root", type=Path)
p.add_argument("episode", type=Path)
p.add_argument("--pitch-deg", type=float, default=None)
p.add_argument("--folder", default="human")
p.add_argument("--focal-mm", type=float, default=None)
a = p.parse_args()
sys.path.insert(0, str(a.root / "human41"))
from human_control import Human

h = Human()
assert Path(a.folder).name == a.folder
folder = a.episode / a.folder
d = dict(np.load(folder / "human-animation.npz"))
r = json.loads((folder / "retarget-report.json").read_text())
h.world = d["world_transform"]
from camera_frame import reference_pitch, pose_head, eye_camera

reference = d["camera_world"][0]
from pxr import Usd, UsdGeom

meta = json.loads((a.episode / "source/scene-meta.json").read_text())
stage = Usd.Stage.Open(str(a.episode / "source/scene.usdc"))
robot_camera = UsdGeom.Camera(stage.GetPrimAtPath(meta["camera_path"]))
reference_focal = float(
    robot_camera.GetFocalLengthAttr().Get() * 36 / robot_camera.GetHorizontalApertureAttr().Get()
)
pitch_deg = reference_pitch(reference) if a.pitch_deg is None else a.pitch_deg
focal_mm = reference_focal if a.focal_mm is None else a.focal_mm
for i, local in enumerate(d["local"]):
    pose = pose_head(h, local, pitch_deg)
    d["local"][i] = pose
    d["camera_world_usd"][i] = eye_camera(h, pose, pitch_deg)
C = d["camera_world_usd"][0]
assert np.max(np.abs(d["camera_world_usd"] - C)) < 1e-7
assert np.allclose(h.world[:3, :3], np.diag([-1.0, -1.0, 1.0]))
np.savez_compressed(folder / "human-animation.npz", **d)
r["gaze"] = {
    "method": "Fixed native eye pose; robot head-camera reference; table-aligned heading and zero roll",
    "pitch_deg": pitch_deg,
    "focal_length_mm": focal_mm,
    "robot_reference_focal_equivalent_mm": reference_focal,
    "framing": "Robot reference pitch and normalized lens by default; table-normal yaw and zero roll; no per-frame tracking",
    "follow_object": False,
    "camera_policy": "Fixed head/eye, not tracking hands; full observer body, first-person head visibility mask",
    "robot_head_position_m": reference[:3, 3].tolist(),
    "human_eye_position_m": C[:3, 3].tolist(),
    "position_delta_m": (C[:3, 3] - reference[:3, 3]).tolist(),
    "position_distance_m": float(np.linalg.norm(C[:3, 3] - reference[:3, 3])),
    "rotation_delta_deg": float(
        np.rad2deg(Rotation.from_matrix(reference[:3, :3].T @ C[:3, :3]).magnitude())
    ),
}
(folder / "retarget-report.json").write_text(json.dumps(r, indent=2))
print("GAZE_DONE", r["gaze"])
