"""Exercise the actual WorldRecorder with a known metric cube trajectory."""

import argparse, json, pickle
from pathlib import Path
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
args, _ = ap.parse_known_args()
out = Path(args.out)
out.mkdir(parents=True, exist_ok=True)
try:
    from isaacsim import SimulationApp
except ImportError:
    from omni.isaac.kit import SimulationApp
app = SimulationApp({"headless": True, "multi_gpu": False, "width": 320, "height": 240})
try:
    from omni.isaac.core import World
    from omni.isaac.core.objects import DynamicCuboid
    from omni.isaac.core.utils.xforms import get_world_pose
    from deps.world_toolkit.world_recorder import WorldRecorder
    from pxr import UsdGeom, Gf, UsdLux

    world = World(stage_units_in_meters=1.0)
    cube = world.scene.add(
        DynamicCuboid(
            prim_path="/World/RecordedCube",
            name="cube",
            position=np.array([0, 0, 0.5]),
            scale=np.array([0.05] * 3),
        )
    )
    UsdLux.DomeLight.Define(world.stage, "/World/TestLight").CreateIntensityAttr(1000.0)
    world.reset()
    recorder = WorldRecorder(world, {}, {"cube": cube}, step_replay=False)
    positions = []
    for i in range(30):
        p = np.array([i * 0.005, 0, 0.5 + 0.08 * np.sin(np.pi * i / 29)])
        # Exercise USD geometric animation directly; PhysX set_world_pose is
        # not flushed to USD until a simulation update in Isaac Sim 5.1.
        cube.prim.GetAttribute("xformOp:translate").Set(Gf.Vec3d(*p.tolist()))
        recorder.record()
        positions.append(p)
    data = recorder.dumps()
    (out / "recorder.pkl").write_bytes(data)
    # Explicitly synthetic fixture for testing the scene/video replay entrypoint.
    (out / "synthetic-fixture.pkl").write_bytes(
        pickle.dumps((pickle.dumps({"synthetic_test": True}), data, pickle.dumps({})))
    )
    world.stage.Flatten().Export(str(out / "synthetic-fixture.scene.usdc"))
    (out / "synthetic-fixture.meta.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "physics_dt": world.get_physics_dt(),
                "prim_paths": [str(p.GetPath()) for p in recorder.xform_prims],
                "object_paths": {"cube": "/World/RecordedCube"},
                "robot_roots": [],
                "end_effector_paths": {},
            }
        )
    )
    recorder.reset()
    recorder.loads(data)
    callback_frames = []
    errors = []

    def before_render(i):
        callback_frames.append(i)
        actual, _ = get_world_pose("/World/RecordedCube")
        errors.append(float(np.linalg.norm(actual - positions[i])))

    recorder.before_render = before_render
    while not recorder.replay():
        pass
    assert callback_frames == list(range(30)), callback_frames
    assert max(errors) < 1e-6, max(errors)
    bad = pickle.loads(data)
    bad["prim_paths"] = ["/wrong"]
    rejected = False
    try:
        recorder.loads(pickle.dumps(bad))
    except ValueError:
        rejected = True
    assert rejected
    result = {
        "frames": 30,
        "max_position_error_m": max(errors),
        "callback_exact_frame_order": True,
        "wrong_prim_path_rejected": True,
        "mode": "prim_pose",
    }
    (out / "result.json").write_text(json.dumps(result, indent=2))
    print("RECORDER_RESULT", result, flush=True)
except BaseException:
    import traceback

    traceback.print_exc()
    raise
finally:
    app.close()
