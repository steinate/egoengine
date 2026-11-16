import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--out", required=True)
args, _ = parser.parse_known_args()
out = Path(args.out)
out.mkdir(parents=True, exist_ok=True)

from isaacsim import SimulationApp

app = SimulationApp(
    {
        "headless": True,
        "width": 320,
        "height": 240,
        "multi_gpu": False,
        "renderer": "RayTracedLighting",
    }
)
try:
    from omni.isaac.core import World
    from omni.isaac.core.objects import DynamicCuboid
    from omni.isaac.sensor import Camera
    import numpy as np
    from PIL import Image

    world = World(stage_units_in_meters=1.0)
    world.scene.add_default_ground_plane()
    world.scene.add(
        DynamicCuboid(
            prim_path="/World/cube",
            name="cube",
            position=np.array([0.0, 0.0, 0.1]),
            scale=np.array([0.1, 0.1, 0.1]),
            color=np.array([0.8, 0.15, 0.1]),
        )
    )
    cam = Camera(
        prim_path="/World/camera",
        position=np.array([0.6, 0.6, 0.5]),
        resolution=(320, 240),
        frequency=30,
    )
    cam.set_world_pose(
        position=np.array([0.6, 0.6, 0.5]),
        orientation=np.array([0.853553, 0.146447, 0.353553, 0.353553]),
        camera_axes="world",
    )
    cam.initialize()
    world.reset()
    for _ in range(30):
        world.step(render=True)
    rgba = cam.get_rgba()
    result = {"rgba_shape": list(rgba.shape), "std": float(rgba[..., :3].std()) if rgba.size else 0}
    if rgba.size:
        Image.fromarray(rgba.astype(np.uint8)).save(out / "smoke.png")
    (out / "smoke.json").write_text(json.dumps(result, indent=2))
    print("SMOKE_RESULT", json.dumps(result), flush=True)
finally:
    app.close()
