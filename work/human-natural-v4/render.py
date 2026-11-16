"""Render exact official episode with a human actor in Isaac Sim 4.1."""

import sys, json, argparse, hashlib, time
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--preview", action="store_true")
p.add_argument("--frames", default="")
p.add_argument("--start", type=int, default=0)
p.add_argument("--end", type=int)
p.add_argument("--job", default="")
p.add_argument("--view", choices=["both", "ego", "front"], default="both")
p.add_argument("--quality", choices=["debug", "final"], default="debug")
p.add_argument(
    "--stride", type=int, default=1, help="Source frame stride; never changes source time"
)
p.add_argument("--output", default="", help="Separate output directory name under the actor folder")
p.add_argument(
    "--audit-sync", action="store_true", help="Capture last/first/last to detect stale GPU geometry"
)
a = p.parse_args()
if a.stride < 1 or (a.output and Path(a.output).name != a.output):
    p.error("stride must be positive; output must be a directory name")
if a.audit_sync and not a.output:
    p.error("--audit-sync requires a separate --output directory")
WIDTH, HEIGHT = (640, 360) if a.quality == "debug" else (1280, 720)
RENDERER = "RayTracedLighting" if a.quality == "debug" else "PathTracing"
START_TIME = time.perf_counter()
tag = a.view + ("-" + a.job if a.job else "")
CODE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
ROOT = Path("/vepfs/public/pengjiaqi/interndata-human-pair")
BASE = ROOT / "human-natural-v4"
OUT = BASE / (a.output or ("preview" if a.preview else "render"))
OUT.mkdir(exist_ok=True)
sys.argv = [
    sys.argv[0],
    "--allow-root",
    "--portable-root",
    str(ROOT / ("cache41/kit-v3-" + tag)),
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
        "width": WIDTH,
        "height": HEIGHT,
        "renderer": RENDERER,
        "anti_aliasing": 0 if a.quality == "debug" else 3,
    }
)
try:
    import carb

    if a.quality == "final":
        assert Path("/usr/share/nvidia/nvoptix.bin").is_file(), "Missing OptiX denoiser data"
        carb.settings.get_settings().set("/rtx/pathtracing/optixDenoiser/enabled", True)
    import numpy as np, omni.usd
    import omni.replicator.core as rep
    from omni.isaac.core import World
    from omni.isaac.core.utils.stage import is_stage_loading
    from omni.isaac.core.prims import XFormPrim
    from pxr import Usd, UsdGeom, UsdPhysics, Gf, Vt
    from PIL import Image
    from scipy.spatial.transform import Rotation

    source = BASE / "human-animation.npz"
    data = np.load(source)
    cache = BASE / "skin-cache"
    manifest = json.loads((cache / "manifest.json").read_text())
    original = ROOT / "human-stack-v3/source"
    meta = json.loads((original / "scene-meta.json").read_text())
    assert hashlib.sha256(source.read_bytes()).hexdigest() == manifest["source_sha256"]
    assert manifest["max_usd_fk_position_error_m"] < 1e-5
    clean = Usd.Stage.Open(str(original / "source-scene.usdc"))
    for path in ["/Render", "/Replicator", "/Orchestrator", meta["robot_root"]]:
        if clean.GetPrimAtPath(path):
            clean.RemovePrim(path)
    for prim in list(clean.Traverse()):
        if prim.GetTypeName() == "PhysicsScene":
            clean.RemovePrim(prim.GetPath())
        else:
            # This is immutable visual replay. Remove inherited robot collision
            # cooking and dynamics while retaining every visible scene mesh.
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
    W = data["world_transform"].copy()
    W[:3, :3] *= 0.01
    root.AddTransformOp().Set(Gf.Matrix4d(W.T.tolist()))

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
    pose = data["local"][0].copy()
    for j, parent in enumerate(data["parents"]):
        pose[j] = (data["world_transform"] if parent < 0 else pose[parent]) @ pose[j]
    names = [str(n).split("/")[-1] for n in data["names"]]
    head = pose[names.index("Head"), :3, 3]
    feet = pose[[names.index("L_Foot"), names.index("R_Foot")], :3, 3].mean(0)
    center = (head + feet) * 0.5
    center[2] += 0.05
    front_eye = center + [0, 2.6, 0.18]
    front_eye[2] = max(front_eye[2], 1.30)
    front_T = look(front_eye, center)
    configs["front"] = front_T
    if a.view != "both":
        configs = {a.view: configs[a.view]}
    annotators = {}
    camops = {}
    products = []
    for name, T in configs.items():
        c = UsdGeom.Camera.Define(stage, "/World/" + name)
        camops[name] = c.AddTransformOp()
        camops[name].Set(Gf.Matrix4d(T.T.tolist()))
        c.CreateFocalLengthAttr(17.0 if name == "ego" else 25.5)
        c.CreateHorizontalApertureAttr(36.0)
        c.CreateVerticalApertureAttr(20.25)
        c.CreateClippingRangeAttr(Gf.Vec2f(0.045 if name == "ego" else 0.025, 100.0))
        rp = rep.create.render_product(str(c.GetPath()), (WIDTH, HEIGHT))
        an = rep.AnnotatorRegistry.get_annotator("rgb")
        an.attach([rp])
        annotators[name] = an
        products.append(rp)
        (OUT / name).mkdir(exist_ok=True)
    schedule = json.loads((original / "contact-schedule.json").read_text())

    def event_frames(value):
        if isinstance(value, dict):
            return [
                i for k, v in value.items() if k not in ("frames", "fps") for i in event_frames(v)
            ]
        return [value] if isinstance(value, int) else []

    frame_count = len(data["source_frame"])
    samples = (
        sorted(set([0, frame_count - 1] + event_frames(schedule)))
        if a.preview
        else list(
            range(a.start, min(a.end if a.end is not None else frame_count, frame_count), a.stride)
        )
    )
    if a.frames:
        samples = [int(i) for i in a.frames.split(",")]
    elif not a.preview and a.stride > 1 and samples:
        last = min(a.end if a.end is not None else frame_count, frame_count) - 1
        if samples[-1] != last:
            samples.append(last)
    if a.audit_sync:
        samples = [
            int(data["source_frame"][-1]),
            int(data["source_frame"][0]),
            int(data["source_frame"][-1]),
        ]
    assert samples and all(i in data["source_frame"] for i in samples)
    audit_images = {}
    frame_seconds = []
    previous = None
    position_errors = []
    rotation_errors = []
    for count, i in enumerate(samples):
        frame_start = time.perf_counter()
        di = int(np.where(data["source_frame"] == i)[0][0])
        if previous is not None:
            for old in previous:
                stage.RemovePrim(old)
        paths = {}
        baked = np.load(cache / f"{i:04d}.npz")
        for variant in annotators:
            # A fresh prim is intentional: in-place point updates produced stale
            # GPU hand geometry while CPU transforms already held the new frame.
            path = f"/World/Human/{variant}_{i:04d}_{count:04d}"
            paths[variant] = path
            avatar = stage.DefinePrim(path, "Xform")
            avatar.GetReferences().AddReference(
                str(cache / ("ego-template.usdc" if variant == "ego" else "visual-template.usdc")),
                "/Worker",
            )
            for j, original_path in enumerate(manifest["mesh_paths"]):
                mesh = UsdGeom.Mesh(stage.GetPrimAtPath(path + original_path[len("/Worker") :]))
                mesh.GetPointsAttr().Set(Vt.Vec3fArray.FromNumpy(baked[f"points_{j}"]))
                mesh.GetNormalsAttr().Set(Vt.Vec3fArray.FromNumpy(baked[f"normals_{j}"]))
                mesh.SetNormalsInterpolation("vertex")
            UsdGeom.Imageable(avatar).MakeInvisible()
        previous = list(paths.values())
        for n, obj in objects.items():
            T = data[n + "_world"][di]
            q = Rotation.from_matrix(T[:3, :3]).as_quat()[[3, 0, 1, 2]]
            obj.set_world_pose(T[:3, 3], q)
        if "ego" in camops:
            camops["ego"].Set(Gf.Matrix4d(data["camera_world_usd"][di].T.tolist()))
        for name, an in annotators.items():
            for variant, path in paths.items():
                im = UsdGeom.Imageable(stage.GetPrimAtPath(path))
                if variant == name:
                    im.MakeVisible()
                else:
                    im.MakeInvisible()
            settings = carb.settings.get_settings()
            if a.quality == "debug":
                # No temporal AA: it can blend previous poses into fast motion.
                # Keep the original pipeline's geometry-settling protocol.
                for _ in range(5 if count == 0 else 3):
                    rep.orchestrator.step(rt_subframes=3, pause_timeline=True, delta_time=1 / 30)
            else:
                settings.set("/rtx/pathtracing/totalSpp", 1)
                settings.set("/rtx/pathtracing/spp", 1)
                for _ in range(3):
                    rep.orchestrator.step(rt_subframes=2, pause_timeline=True, delta_time=1 / 30)
                settings.set("/rtx/pathtracing/totalSpp", 64)
                settings.set("/rtx/pathtracing/spp", 64)
                for _ in range(2):
                    rep.orchestrator.step(rt_subframes=1, pause_timeline=True, delta_time=1 / 30)
            rgb = np.asarray(an.get_data())[..., :3].copy()
            assert rgb.shape == (HEIGHT, WIDTH, 3) and rgb.std() > 1
            filename = f"{count:04d}-source-{i:04d}.png" if a.audit_sync else f"{i:04d}.png"
            Image.fromarray(rgb).save(OUT / name / filename, compress_level=1)
            if a.audit_sync and count in (0, 2):
                audit_images[name, count] = rgb
        for n, obj in objects.items():
            pos, q = obj.get_world_pose()
            position_errors.append(float(np.linalg.norm(pos - data[n + "_world"][di, :3, 3])))
            R = Rotation.from_quat(q[[1, 2, 3, 0]]).as_matrix()
            rotation_errors.append(
                float(Rotation.from_matrix(R.T @ data[n + "_world"][di, :3, :3]).magnitude())
            )
        frame_seconds.append(time.perf_counter() - frame_start)
        if count % 20 == 0 or a.preview or a.audit_sync:
            print(
                "RENDERED",
                i,
                "pos_error",
                max(position_errors),
                "rot_error",
                max(rotation_errors),
                "seconds_per_source_frame",
                round(float(np.mean(frame_seconds[-20:])), 3),
                flush=True,
            )
    result = {
        "frames": len(samples),
        "fps": 15,
        "source_frames": samples,
        "source_world_tracks_sha256": json.loads((BASE / "retarget-report.json").read_text())[
            "source_sha256"
        ],
        "source_animation_sha256": manifest["source_sha256"],
        "render_script_sha256": CODE_SHA256,
        "max_object_position_error_m": max(position_errors),
        "max_object_rotation_error_rad": max(rotation_errors),
        "max_usd_fk_position_error_m": manifest["max_usd_fk_position_error_m"],
        "renderer": settings.get("/rtx/rendermode"),
        "requested_renderer": RENDERER,
        "quality": a.quality,
        "resolution": [WIDTH, HEIGHT],
        "stride": a.stride,
        "source_episode_frames": frame_count,
        "source_time_s": [
            float(data["video_time_s"][int(np.where(data["source_frame"] == i)[0][0])])
            for i in samples
        ],
        "wall_seconds": time.perf_counter() - START_TIME,
        "mean_seconds_per_source_frame": float(np.mean(frame_seconds)),
        "geometry_update": "new avatar prim for each source frame; settled before RGB capture",
        "camera": "Ego from posed eye bones; closer frontal full-body observer",
        "front_camera_world_usd": front_T.tolist(),
        "front_focal_length_mm": 25.5,
        "camera_K": [[WIDTH * 17 / 36, 0, WIDTH / 2], [0, WIDTH * 17 / 36, HEIGHT / 2], [0, 0, 1]],
        "physics": "Replay of verified stable-stack robot episode generated by official pipeline with task-local placement fixes; no new human dynamics simulation",
        "scene": "Original saved official stage with robot removed and full human character substituted",
        "light_intensity_multiplier": 0.18,
        "ego_visibility": "Own head, face and hat hidden for first person; full avatar used in observer view",
    }
    if a.audit_sync:
        result["sync_audit"] = {
            name: {
                "repeat_frame_mae_255": float(
                    np.abs(audit_images[name, 0].astype(float) - audit_images[name, 2]).mean()
                )
            }
            for name in annotators
        }
        result["sync_audit_passed"] = all(
            v["repeat_frame_mae_255"] < 5.0 for v in result["sync_audit"].values()
        )
    (OUT / ("verification-" + tag + ".json")).write_text(json.dumps(result, indent=2))
    assert result["renderer"] == RENDERER, "Actual renderer differs from requested profile"
    if a.audit_sync:
        assert result["sync_audit_passed"], (
            "Repeated pose changed after a frame jump; inspect saved RGB before rendering video"
        )
    print("RENDER_DONE", json.dumps(result), flush=True)
except BaseException:
    import traceback

    traceback.print_exc()
    raise
finally:
    app.close(wait_for_replicator=False)
