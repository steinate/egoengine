"""Render exact official episode with a human actor in Isaac Sim 4.1."""

import sys, json, argparse, hashlib, time
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--frames", default="")
p.add_argument("--preview", action="store_true")
p.add_argument("--start", type=int, default=0)
p.add_argument("--end", type=int)
p.add_argument("--job", default="")
p.add_argument("--view", choices=["both", "ego", "front"], default="both")
a = p.parse_args()
tag = a.view + ("-" + a.job if a.job else "")
RENDER_CODE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
OPTIX_WEIGHTS = Path("/usr/share/nvidia/nvoptix.bin")
if not OPTIX_WEIGHTS.is_file():
    raise RuntimeError(
        "OptiX denoiser data is missing. See migration/FRESH_EPISODE.md and bootstrap_optix.sh."
    )
OPTIX_WEIGHTS_SHA256 = hashlib.sha256(OPTIX_WEIGHTS.read_bytes()).hexdigest()
ROOT = Path("/vepfs/public/pengjiaqi/interndata-human-pair")
BASE = ROOT / "anime-human-v1"
OLD = BASE
OUT = BASE / ("preview" if a.preview else "render")
OUT.mkdir(exist_ok=True)
sys.argv = [
    sys.argv[0],
    "--allow-root",
    "--portable-root",
    str(ROOT / ("cache41/kit-anime-" + tag)),
    f"--/log/file={OUT}/kit-{tag}.log",
    "--/app/hydraEngine/waitIdle=true",
    "--/app/updateOrder/checkForHydraRenderComplete=1000",
    "--/app/useFabricSceneDelegate=false",
]
from omni.isaac.kit import SimulationApp

app = SimulationApp(
    {
        "headless": True,
        "multi_gpu": False,
        "width": 1280,
        "height": 720,
        "renderer": "PathTracing",
        "anti_aliasing": 3,
    }
)
try:
    import carb

    carb.settings.get_settings().set("/rtx/pathtracing/spp", 32)
    carb.settings.get_settings().set("/rtx/pathtracing/totalSpp", 64)
    carb.settings.get_settings().set("/rtx/pathtracing/optixDenoiser/enabled", True)
    import numpy as np, omni.usd
    import omni.replicator.core as rep
    from omni.isaac.core import World
    from omni.isaac.core.utils.stage import is_stage_loading
    from omni.isaac.core.prims import XFormPrim
    from pxr import Usd, UsdGeom, UsdPhysics, Gf, Vt
    from PIL import Image
    from scipy.spatial.transform import Rotation

    source = BASE / "anime-animation.npz"
    data = np.load(source)
    cache = BASE / "skin-cache"
    manifest = json.loads((cache / "manifest.json").read_text())
    original = BASE / "source"
    meta = json.loads((original / "scene-meta.json").read_text())
    assert hashlib.sha256(source.read_bytes()).hexdigest() == manifest["animation_sha256"]
    clean = Usd.Stage.Open(str(original / "source-scene.usdc"))
    for path in ["/Render", "/Replicator", "/Orchestrator", meta["robot_root"]]:
        if clean.GetPrimAtPath(path):
            clean.RemovePrim(path)
    for prim in list(clean.Traverse()):
        if prim.GetTypeName() == "PhysicsScene":
            clean.RemovePrim(prim.GetPath())
        else:
            for api in [
                UsdPhysics.CollisionAPI,
                UsdPhysics.MeshCollisionAPI,
                UsdPhysics.RigidBodyAPI,
                UsdPhysics.MassAPI,
            ]:
                if prim.HasAPI(api):
                    prim.RemoveAPI(api)
    clean.Export(str(BASE / ("replay-scene-" + tag + ".usdc")))
    del clean
    omni.usd.get_context().open_stage(str(BASE / ("replay-scene-" + tag + ".usdc")))
    while is_stage_loading():
        app.update()
    world = World(stage_units_in_meters=1.0, physics_dt=1 / 30, rendering_dt=1 / 30)
    world.reset()
    stage = world.stage
    for prim in stage.Traverse():
        intensity = prim.GetAttribute("inputs:intensity")
        if intensity and intensity.Get() is not None:
            intensity.Set(float(intensity.Get()) * 0.18)
    objects = {n: XFormPrim(m["prim_path"]) for n, m in meta["objects"].items()}
    root = UsdGeom.Xform.Define(stage, "/World/Human")

    def look(eye, target):
        eye = np.array(eye)
        z = eye - np.array(target)
        z /= np.linalg.norm(z)
        x = np.cross([0, 0, 1], z)
        x /= np.linalg.norm(x)
        y = np.cross(z, x)
        T = np.eye(4)
        T[:3, :3] = np.stack([x, y, z], 1)
        T[:3, 3] = eye
        return T

    configs = {"ego": data["camera_world_usd"][0]}
    front_T = look([0.05, 2.10, 0.95], [0.05, -0.50, 0.52])
    configs["front"] = front_T
    if a.view != "both":
        configs = {a.view: configs[a.view]}
    annotators = {}
    capture = UsdGeom.Camera.Define(stage, "/World/CaptureCamera")
    capture_op = capture.AddTransformOp()
    capture.CreateHorizontalApertureAttr(36.0)
    capture.CreateVerticalApertureAttr(20.25)
    rp = rep.create.render_product(str(capture.GetPath()), (1280, 720))
    capture_an = rep.AnnotatorRegistry.get_annotator("rgb")
    capture_an.attach([rp])
    for name in configs:
        annotators[name] = capture_an
        (OUT / name).mkdir(exist_ok=True)
    samples = (
        [
            i
            for i in [0, 137, 258, 433, 474, 780, 1006, 1044, 1130, 1331, 1506]
            if i in data["source_frame"]
        ]
        if a.preview
        else list(
            range(a.start, min(a.end or len(data["source_frame"]), len(data["source_frame"])))
        )
    )
    previous = None
    position_errors = []
    rotation_errors = []
    if a.frames:
        samples = [int(v) for v in a.frames.split(",")]
    animation_hash = manifest["animation_sha256"]
    paths = {}
    body_meshes = {}
    for variant in annotators:
        path = f"/World/Human/{variant}"
        paths[variant] = path
        avatar = stage.DefinePrim(path, "Xform")
        avatar.GetReferences().AddReference(str(BASE / (variant + "-template.usdc")), "/Amber")
        body_meshes[variant] = [UsdGeom.Mesh(stage.GetPrimAtPath(path + "/Body"))]
        UsdGeom.Imageable(avatar).MakeInvisible()
    for count, i in enumerate(samples):
        frame_start = time.monotonic()
        di = int(np.where(data["source_frame"] == i)[0][0])
        baked = np.load(cache / f"{i:04d}.npz")
        assert str(baked["animation_sha256"]) == animation_hash
        assert int(baked["source_frame"]) == i
        for meshes in body_meshes.values():
            mesh = meshes[0]
            mesh.GetPointsAttr().Set(Vt.Vec3fArray.FromNumpy(baked["points"]))
            mesh.GetNormalsAttr().Set(Vt.Vec3fArray.FromNumpy(baked["normals"]))
            mesh.SetNormalsInterpolation("vertex")
        for n, obj in objects.items():
            T = data[n + "_world"][di]
            q = Rotation.from_matrix(T[:3, :3]).as_quat()[[3, 0, 1, 2]]
            obj.set_world_pose(T[:3, 3], q)
        for name, an in annotators.items():
            T = data["camera_world_usd"][di] if name == "ego" else front_T
            capture_op.Set(Gf.Matrix4d(T.T.tolist()))
            capture.GetFocalLengthAttr().Set(17.0 if name == "ego" else 24.0)
            capture.GetClippingRangeAttr().Set(Gf.Vec2f(0.045 if name == "ego" else 0.025, 100.0))
            for variant, path in paths.items():
                im = UsdGeom.Imageable(stage.GetPrimAtPath(path))
                if variant == name:
                    im.MakeVisible()
                else:
                    im.MakeInvisible()
            settings = carb.settings.get_settings()
            settings.set("/rtx/pathtracing/totalSpp", 1)
            settings.set("/rtx/pathtracing/spp", 1)
            for _ in range(3):
                rep.orchestrator.step(rt_subframes=2, pause_timeline=True, delta_time=1 / 30)
            settings.set("/rtx/pathtracing/totalSpp", 64)
            settings.set("/rtx/pathtracing/spp", 64)
            for _ in range(4 if count == 0 else 1):
                rep.orchestrator.step(rt_subframes=1, pause_timeline=True, delta_time=1 / 30)
            rgb = np.asarray(an.get_data())[..., :3].copy()
            assert rgb.shape == (720, 1280, 3) and rgb.std() > 1
            Image.fromarray(rgb).save(OUT / name / f"{i:04d}.png")
        for n, obj in objects.items():
            pos, q = obj.get_world_pose()
            position_errors.append(float(np.linalg.norm(pos - data[n + "_world"][di, :3, 3])))
            R = Rotation.from_quat(q[[1, 2, 3, 0]]).as_matrix()
            rotation_errors.append(
                float(Rotation.from_matrix(R.T @ data[n + "_world"][di, :3, :3]).magnitude())
            )
        if count % 20 == 0 or a.preview:
            print(
                "RENDERED",
                i,
                "pos_error",
                max(position_errors),
                "rot_error",
                max(rotation_errors),
                "seconds",
                round(time.monotonic() - frame_start, 3),
                flush=True,
            )
    result = {
        "render_script_sha256": RENDER_CODE_SHA256,
        "animation_sha256": animation_hash,
        "frames": len(samples),
        "fps": 15,
        "source_frames": samples,
        "max_object_position_error_m": max(position_errors),
        "max_object_rotation_error_rad": max(rotation_errors),
        "renderer": "Isaac Sim 4.1 RTX PathTracing 64 SPP",
        "optix_weights_sha256": OPTIX_WEIGHTS_SHA256,
        "actor": "Genshin Impact Amber; original PMX mesh, UVs, textures and skin weights; native humanoid IK",
        "front_camera_world_usd": front_T.tolist(),
        "front_focal_length_mm": 24.0,
        "camera_K": [[1280 * 17 / 36, 0, 640], [0, 1280 * 17 / 36, 360], [0, 0, 1]],
        "physics": "Original verified robot trajectory replay; no new human dynamics simulation",
        "scene": "Original saved official-pipeline scene with robot replaced by Amber",
    }
    (OUT / ("verification-" + tag + ".json")).write_text(json.dumps(result, indent=2))
    print("RENDER_DONE", json.dumps(result), flush=True)
except BaseException:
    import traceback

    traceback.print_exc()
    raise
finally:
    app.close(wait_for_replicator=False)
