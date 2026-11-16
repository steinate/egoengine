"""Render an exported plan/scene directly; no replanning or physical stepping.

Without --human-mesh, renders robot baseline. With it, hides robot roots and
updates MANO/arm geometry using the pre-render callback. This needs the patched
plan's .meta.json and .scene.usdc sidecars, and accessible referenced textures.
"""

import argparse, json, pickle, sys
from pathlib import Path
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("--plan", required=True)
ap.add_argument("--output", required=True)
ap.add_argument("--width", type=int, default=1280)
ap.add_argument("--height", type=int, default=720)
ap.add_argument("--focal-length-usd", type=float, default=18.0)
ap.add_argument("--human-mesh")
ap.add_argument("--max-frames", type=int)
ap.add_argument("--eye", type=float, nargs=3, default=[0.0, -0.65, 1.45])
ap.add_argument("--target", type=float, nargs=3, default=[0.0, 0.0, 0.85])
args, kit_args = ap.parse_known_args()
deploy = Path(__file__).resolve().parents[3]
if "--portable-root" not in kit_args:
    kit_args = ["--portable-root", str(deploy / "cache41/kit")] + kit_args
sys.argv = [
    sys.argv[0],
    "--allow-root",
    f"--/structuredLog/logDirectory={deploy}/logs41/structured",
    f"--/log/file={deploy}/logs41/kit-replay.log",
] + kit_args
path = Path(args.plan)
out = Path(args.output)
out.parent.mkdir(parents=True, exist_ok=True)
cfg_b, rec_b, log_b = pickle.loads(path.read_bytes())
rec = pickle.loads(rec_b)
meta = json.loads(path.with_suffix(".meta.json").read_text())
if rec.get("mode") != "prim_pose":
    raise ValueError("Visual replay requires prim_pose data")
if rec.get("prim_paths") != meta["prim_paths"]:
    raise ValueError("Prim manifest mismatch")
try:
    from isaacsim import SimulationApp
except ImportError:
    from omni.isaac.kit import SimulationApp
app = SimulationApp(
    {"headless": True, "multi_gpu": False, "width": args.width, "height": args.height}
)
try:
    import omni.usd
    from omni.isaac.core import World
    from omni.isaac.sensor import Camera
    from omni.isaac.core.utils.stage import is_stage_loading
    from omni.isaac.core.utils.xforms import get_world_pose
    from deps.world_toolkit.world_recorder import WorldRecorder
    from scipy.spatial.transform import Rotation
    import imageio.v2 as imageio

    omni.usd.get_context().open_stage(str(path.with_suffix(".scene.usdc")))
    while is_stage_loading():
        app.update()
    world = World(
        stage_units_in_meters=1.0, physics_dt=meta["physics_dt"], rendering_dt=meta["physics_dt"]
    )
    # Initialize the loaded stage and timeline once so camera annotators emit
    # data. Every saved pose is restored afterwards; the replay loop only renders.
    world.reset()
    recorder = WorldRecorder(world, {}, {}, step_replay=False)
    recorder.xform_prims = [world.stage.GetPrimAtPath(p) for p in meta["prim_paths"]]
    if any(not p.IsValid() for p in recorder.xform_prims):
        raise ValueError("Missing recorded prim")
    recorder.loads(rec_b)
    if args.human_mesh:
        from .overlay import HumanOverlay

        overlay = HumanOverlay(world.stage, args.human_mesh, meta["robot_roots"])
        if len(overlay.data["vertices"]) != recorder.num_steps:
            raise ValueError("Human/robot frame count mismatch")
        recorder.before_render = overlay
    eye = np.array(args.eye)
    target = np.array(args.target)
    z = eye - target
    z /= np.linalg.norm(z)
    x = np.cross([0.0, 0.0, 1.0], z)
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    q = Rotation.from_matrix(np.stack([x, y, z], axis=1)).as_quat()[[3, 0, 1, 2]]
    cam = Camera(
        prim_path="/World/HumanEgoCamera",
        resolution=(args.width, args.height),
        frequency=round(1 / meta["physics_dt"]),
    )
    cam.set_world_pose(eye, q, camera_axes="usd")
    cam.set_clipping_range(0.01, 100.0)
    cam.initialize()
    world.stage.GetPrimAtPath("/World/HumanEgoCamera").GetAttribute("focalLength").Set(
        args.focal_length_usd
    )
    for _ in range(15):
        recorder._replay_from_prim_poses(increment_counter=False)
    limit = min(recorder.num_steps, args.max_frames or recorder.num_steps)
    errors = []
    angle_errors = []
    frames = 0
    with imageio.get_writer(
        out, fps=1 / meta["physics_dt"], codec="libx264", quality=8, macro_block_size=1
    ) as writer:
        for i in range(limit):
            recorder.replay()
            rgba = cam.get_rgba()
            if rgba.shape != (args.height, args.width, 4):
                raise ValueError(f"Invalid camera output: {rgba.shape}")
            rgb = rgba[:, :, :3].astype(np.uint8)
            if i == 0:
                imageio.imwrite(out.with_suffix(".png"), rgb)
            writer.append_data(rgb)
            frames += 1
            for prim_path in meta["object_paths"].values():
                if prim_path in meta["prim_paths"]:
                    j = meta["prim_paths"].index(prim_path)
                    p, actual_q = get_world_pose(prim_path)
                    errors.append(float(np.linalg.norm(p - np.array(rec["prim_poses"][i][j][0]))))
                    expected_q = np.array(rec["prim_poses"][i][j][1])
                    actual_q = np.array(actual_q)
                    similarity = abs(np.dot(expected_q, actual_q)) / (
                        np.linalg.norm(expected_q) * np.linalg.norm(actual_q)
                    )
                    angle_errors.append(float(np.degrees(2 * np.arccos(np.clip(similarity, 0, 1)))))
    result = {
        "frames": frames,
        "human_mesh": bool(args.human_mesh),
        "max_object_position_error_m": max(errors, default=0),
        "max_object_rotation_error_deg": max(angle_errors, default=0),
        "eye": args.eye,
        "target": args.target,
        "source_plan": str(path),
    }
    out.with_suffix(".json").write_text(json.dumps(result, indent=2))
    print("REPLAY_RESULT", result, flush=True)
except BaseException:
    import traceback

    traceback.print_exc()
    raise
finally:
    app.close()
