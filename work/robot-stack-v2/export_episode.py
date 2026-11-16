"""Export a newly verified stack/lift episode for native human contact IK."""

import json, shutil, hashlib, sys, argparse
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation

B = Path(__file__).resolve().parent
ROOT = B.parent
p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--trial", type=Path, required=True)
p.add_argument("--robot-export", type=Path, required=True)
p.add_argument("--output", type=Path, default=ROOT / "human-stack-v3/source")
a = p.parse_args()
OUT = a.output.resolve()
OUT.mkdir(parents=True, exist_ok=True)
if (OUT / "world-tracks.npz").exists():
    raise RuntimeError("Refusing to replace an existing episode")
sys.path.insert(0, str(ROOT / "runtime41/kit/exts/omni.usd.libs"))
from pxr import Usd, UsdGeom

evidence = json.loads((a.trial / "stack-validation.json").read_text())
assert evidence["passed"]
exported = json.loads((a.robot_export / "verification.json").read_text())
assert exported["integrity_passed"]
d = np.load(a.robot_export / "object-and-robot-tracks.npz")
N = len(d["video_frame_index"])
assert N == exported["frames"] == evidence["frames"]
assert np.array_equal(d["video_frame_index"], np.arange(N))
diag = np.load(a.trial / "diagnostic-tracks.npz")
assert len(diag["step"]) == N
for name in ["place_object", "pick_object_left1", "pick_object_right1"]:
    assert np.allclose(d[name + "__translation_local_m"], diag[name][:, :3], atol=1e-7, rtol=0), (
        name
    )
    assert np.allclose(d[name + "__orientation_wxyz"], diag[name][:, 3:], atol=1e-7, rtol=0), name
stage = Usd.Stage.Open(str(a.trial / "initial-scene.usdc"))


def mat(path):
    return np.array(
        UsdGeom.Xformable(stage.GetPrimAtPath(path)).ComputeLocalToWorldTransform(
            Usd.TimeCode.Default()
        )
    ).T


meta = {
    "source": "Verified stable-stack robot episode, seed 42; official pipeline with task-local stable_place skill",
    "objects": {},
    "robot_root": "/World/task_0/split_aloha",
    "frames": N,
    "fps": 15,
    "robot_validation": evidence,
}
data = {
    "recorded_step_index": diag["step"].copy(),
    "video_frame_index": np.arange(N),
    "video_time_s": np.arange(N) / 15.0,
}
for side, key in [("left", "T_base_ee_fl"), ("right", "T_base_ee_fr")]:
    arm = "fl" if side == "left" else "fr"
    path = (
        meta["robot_root"]
        + "/split_aloha_mid_360_with_piper/split_aloha_mid_360_with_piper/"
        + arm
        + "/arm_base"
    )
    base_world = mat(path)
    data[side + "_ee_world"] = base_world @ d[key]
    meta[side + "_base_world"] = base_world.tolist()
for name in ["place_object", "pick_object_left1", "pick_object_right1"]:
    path = f"/World/task_0/{name}/Aligned"
    prim = stage.GetPrimAtPath(path)
    assert prim
    parent = mat(str(prim.GetParent().GetPath()))
    T = np.tile(np.eye(4), (N, 1, 1))
    T[:, :3, :3] = Rotation.from_quat(d[name + "__orientation_wxyz"][:, [1, 2, 3, 0]]).as_matrix()
    T[:, :3, 3] = d[name + "__translation_local_m"]
    data[name + "_world"] = parent @ T
    # Mesh coordinates relative to the actual USD rigid-body frame, removing scale
    # from the body transform while retaining it in the metric vertex coordinates.
    rigid = mat(path)
    rigid[:3, :3] /= np.linalg.norm(rigid[:3, :3], axis=0)
    inverse = np.linalg.inv(rigid)
    vertices = []
    faces = []
    offset = 0
    for pr in Usd.PrimRange(prim):
        if not pr.IsA(UsdGeom.Mesh):
            continue
        mesh = UsdGeom.Mesh(pr)
        v = np.array(mesh.GetPointsAttr().Get())
        X = inverse @ mat(str(pr.GetPath()))
        v = v @ X[:3, :3].T + X[:3, 3]
        counts = mesh.GetFaceVertexCountsAttr().Get()
        idx = np.array(mesh.GetFaceVertexIndicesAttr().Get())
        start = 0
        for count in counts:
            f = idx[start : start + count] + offset
            faces.extend([f[0], f[k], f[k + 1]] for k in range(1, count - 1))
            start += count
        vertices.append(v)
        offset += len(v)
    data[name + "_mesh_vertices"] = np.concatenate(vertices)
    data[name + "_mesh_faces"] = np.array(faces)
    meta["objects"][name] = {
        "prim_path": path,
        "parent_world": parent.tolist(),
        "mesh_bounds_m": [
            data[name + "_mesh_vertices"].min(0).tolist(),
            data[name + "_mesh_vertices"].max(0).tolist(),
        ],
    }
stage.Export(str(OUT / "source-scene.usdc"))
np.savez_compressed(OUT / "world-tracks.npz", **data)
(OUT / "scene-meta.json").write_text(json.dumps(meta, indent=2))
for source, dest in [
    (a.trial / "events.json", OUT / "events.json"),
    (a.robot_export / "verification.json", OUT / "robot-source-verification.json"),
    (a.trial / "stack-validation.json", OUT / "robot-stack-validation.json"),
]:
    shutil.copy(source, dest)
episode = Path(exported["source_episode"])
shutil.copy(episode / "images.rgb.head/demo.mp4", OUT / "robot-full.mp4")
events = json.loads((OUT / "events.json").read_text())


def frame(token):
    return next(e["frame"] for e in events if token in e["phase"])


schedule = {
    "left": {
        "object": "pick_object_left1",
        "begin": 0,
        "grasp": frame("left:Pick:attach_obj"),
        "release": frame("left:StablePlace:open_gripper"),
    },
    "right": {
        "object": "pick_object_right1",
        "begin": frame("right:Pick:update_pose_cost_metric"),
        "grasp": frame("right:Pick:attach_obj"),
        "release": frame("right:StablePlace:open_gripper"),
    },
    "tray": {
        "begin": next(
            e["frame"]
            for e in events
            if "left:Pick:update_pose_cost_metric right:Pick:update_pose_cost_metric" == e["phase"]
        ),
        "grasp": frame("left:Heuristic_Skill:dummy_forward right:Heuristic_Skill:dummy_forward"),
        "end": N - 1,
    },
    "frames": N,
    "fps": 15,
}
for side in ["left", "right"]:
    t = schedule[side]
    assert (
        0
        <= t["begin"]
        < t["grasp"]
        < t["release"]
        < schedule["tray"]["begin"]
        < schedule["tray"]["grasp"]
        < N
    )
(OUT / "contact-schedule.json").write_text(json.dumps(schedule, indent=2))
print(json.dumps(schedule, indent=2))
print("SOURCE_EXPORTED", N, hashlib.sha256((OUT / "world-tracks.npz").read_bytes()).hexdigest())
