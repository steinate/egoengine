"""Synchronized rigid/link replay and fresh native Worker meshes in Isaac Sim 4.1."""

import argparse, json, sys, time, hashlib
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("episode", type=Path)
p.add_argument("--preview", action="store_true")
p.add_argument("--stride", type=int, default=6)
a = p.parse_args()
ep = a.episode.resolve()
base = ep / "human"
out = base / ("preview" if a.preview else "render")
out.mkdir(exist_ok=True)
sys.argv = [
    sys.argv[0],
    "--allow-root",
    "--/app/useFabricSceneDelegate=false",
    "--/app/hydraEngine/waitIdle=true",
    f"--/log/file={out}/kit.log",
]
from omni.isaac.kit import SimulationApp

app = SimulationApp(
    {
        "headless": True,
        "multi_gpu": False,
        "width": 640,
        "height": 360,
        "renderer": "RayTracedLighting",
        "anti_aliasing": 0,
    }
)
try:
    import numpy as np, omni.usd, omni.replicator.core as rep
    from omni.isaac.core import World
    from omni.isaac.core.utils.stage import is_stage_loading
    from pxr import Usd, UsdGeom, UsdPhysics, Gf, Vt
    from PIL import Image

    d = np.load(base / "human-animation.npz")
    meta = json.loads((ep / "source/scene-meta.json").read_text())
    cache = base / "skin-cache"
    manifest = json.loads((cache / "manifest.json").read_text())
    report = json.loads((base / "retarget-report.json").read_text())
    assert (
        hashlib.sha256((ep / "source/world-tracks.npz").read_bytes()).hexdigest()
        == report["source_sha256"]
    )
    assert (
        hashlib.sha256((base / "human-animation.npz").read_bytes()).hexdigest()
        == manifest["source_sha256"]
    )
    clean = Usd.Stage.Open(str(ep / "source/scene.usdc"))
    for path in ["/Render", "/Replicator", "/Orchestrator", meta["robot_root"]]:
        if clean.GetPrimAtPath(path):
            clean.RemovePrim(path)
    for pr in list(clean.Traverse()):
        if pr.GetTypeName() == "PhysicsScene" or pr.IsA(UsdPhysics.Joint):
            clean.RemovePrim(pr.GetPath())
            continue
        for api in [
            UsdPhysics.CollisionAPI,
            UsdPhysics.MeshCollisionAPI,
            UsdPhysics.RigidBodyAPI,
            UsdPhysics.MassAPI,
            UsdPhysics.ArticulationRootAPI,
        ]:
            if pr.HasAPI(api):
                pr.RemoveAPI(api)
    clean.Export(str(base / "replay.usdc"))
    del clean
    omni.usd.get_context().open_stage(str(base / "replay.usdc"))
    while is_stage_loading():
        app.update()
    world = World(stage_units_in_meters=1.0, physics_dt=1 / 30, rendering_dt=1 / 30)
    world.reset()
    stage = world.stage
    for pr in stage.Traverse():
        intensity = pr.GetAttribute("inputs:intensity")
        if intensity and intensity.Get() is not None:
            intensity.Set(float(intensity.Get()) * 0.5)

    def matrix(path):
        return np.asarray(
            UsdGeom.Xformable(stage.GetPrimAtPath(path)).ComputeLocalToWorldTransform(
                Usd.TimeCode.Default()
            )
        ).T

    first_mesh = np.load(cache / "0000.npz")
    native_foot_height = (
        float(
            d["world_transform"][2, 3]
            + min(
                first_mesh[k][:, 2].min() * 0.01
                for k in first_mesh.files
                if k.startswith("points_")
            )
        )
        - 0.005
    )
    replay = []
    for j, path in sorted(enumerate(meta["prim_paths"]), key=lambda x: x[1].count("/")):
        pr = stage.GetPrimAtPath(path)
        if not pr or not UsdGeom.Xformable(pr):
            continue
        x = UsdGeom.Xformable(pr)
        x.ClearXformOpOrder()
        op = x.AddTransformOp()
        replay.append((j, path, str(pr.GetParent().GetPath()), op))
    W = d["world_transform"].copy()
    W[:3, :3] *= 0.01
    UsdGeom.Xform.Define(stage, "/World/Human").AddTransformOp().Set(Gf.Matrix4d(W.T.tolist()))

    def look(eye, target):
        z = np.array(eye) - target
        z /= np.linalg.norm(z)
        x = np.cross([0, 0, 1], z)
        x /= np.linalg.norm(x)
        T = np.eye(4)
        T[:3, :3] = np.stack([x, np.cross(z, x), z], 1)
        T[:3, 3] = eye
        return T

    # Front is along table normal, not avatar shoulder yaw. Equal X eliminates
    # the previous diagonal tabletop perspective. The eye camera is fixed.
    front = look(np.array([0.0, 1.15, 1.3]), np.array([0.0, -0.2, 1.05]))
    ego_focal = report["gaze"].get("focal_length_mm", 10.0)
    assert np.max(np.abs(d["camera_world_usd"] - d["camera_world_usd"][0])) < 1e-7
    annotators = {}
    camops = {}
    for name, T in [("ego", d["camera_world_usd"][0]), ("front", front)]:
        c = UsdGeom.Camera.Define(stage, "/World/PairCamera_" + name)
        camops[name] = c.AddTransformOp()
        camops[name].Set(Gf.Matrix4d(T.T.tolist()))
        c.CreateFocalLengthAttr(ego_focal if name == "ego" else 24.0)
        c.CreateHorizontalApertureAttr(36.0)
        c.CreateVerticalApertureAttr(20.25)
        c.CreateClippingRangeAttr(Gf.Vec2f(0.045, 100))
        rp = rep.create.render_product(str(c.GetPath()), (640, 360))
        an = rep.AnnotatorRegistry.get_annotator("rgb")
        an.attach([rp])
        annotators[name] = an
        (out / name).mkdir(exist_ok=True)
    baked_samples = manifest["samples"]
    N = len(d["source_frame"])
    assert a.stride > 0
    samples = sorted(
        set(
            [i for i in baked_samples if i % a.stride == 0]
            + [N - 1]
            + [
                min(baked_samples, key=lambda i: abs(i - c[k]))
                for c in report["contacts"].values()
                for k in ["grasp", "release"]
            ]
        )
    )
    if a.preview:
        wanted = [0, N - 1, int(np.argmax(d["wrist_targets"][:, :, 2, 3].max(axis=1)))] + [
            v[k] for v in report["contacts"].values() for k in ["grasp", "release"]
        ]
        samples = sorted(set(min(samples, key=lambda s: abs(s - i)) for i in wanted))
    # Audit jumps in this same warm process, then render the entire schedule.
    movement = np.linalg.norm(
        d["wrist_targets"][:, :, :3, 3] - d["wrist_targets"][-1, :, :3, 3], axis=-1
    ).sum(axis=1)
    probe = min(baked_samples, key=lambda i: abs(i - int(np.argmax(movement))))
    schedule = [N - 1, probe, N - 1] + samples
    previous = []
    audit = {}
    errors = []
    started = time.perf_counter()
    for count, i in enumerate(schedule):
        for path in previous:
            stage.RemovePrim(path)
        paths = {}
        baked = np.load(cache / f"{i:04d}.npz")
        for variant in annotators:
            path = f"/World/Human/{variant}_{count:05d}"
            paths[variant] = path
            avatar = stage.DefinePrim(path, "Xform")
            avatar.GetReferences().AddReference(
                str(cache / ("ego-template.usdc" if variant == "ego" else "visual-template.usdc")),
                "/Worker",
            )
            for j, original in enumerate(manifest["mesh_paths"]):
                mesh = UsdGeom.Mesh(stage.GetPrimAtPath(path + original[len("/Worker") :]))
                mesh.GetPointsAttr().Set(Vt.Vec3fArray.FromNumpy(baked[f"points_{j}"]))
                mesh.GetNormalsAttr().Set(Vt.Vec3fArray.FromNumpy(baked[f"normals_{j}"]))
                mesh.SetNormalsInterpolation("vertex")
            UsdGeom.Imageable(avatar).MakeInvisible()
        previous = list(paths.values())
        for j, path, parent, op in replay:
            P = matrix(parent) if parent != "/" else np.eye(4)
            local = np.linalg.inv(P) @ d["prim_world"][i, j]
            op.Set(Gf.Matrix4d(local.T.tolist()))
        camops["ego"].Set(Gf.Matrix4d(d["camera_world_usd"][i].T.tolist()))
        for name, an in annotators.items():
            for variant, path in paths.items():
                im = UsdGeom.Imageable(stage.GetPrimAtPath(path))
                im.MakeVisible() if variant == name else im.MakeInvisible()
            for _ in range(20 if count == 0 else 3):
                rep.orchestrator.step(rt_subframes=3, pause_timeline=True, delta_time=1 / 30)
            rgb = np.asarray(an.get_data())[..., :3].copy()
            if count < 3:
                # Average audit captures to distinguish persistent stale geometry
                # from stochastic RTX lighting noise without loosening the gate.
                captures = [rgb.astype(float)]
                for _ in range(3):
                    rep.orchestrator.step(rt_subframes=3, pause_timeline=True, delta_time=1 / 30)
                    captures.append(np.asarray(an.get_data())[..., :3].astype(float))
                rgb = np.mean(captures, axis=0).round().astype(np.uint8)
                (out / "sync-audit").mkdir(exist_ok=True)
                Image.fromarray(rgb).save(out / "sync-audit" / f"{name}-{count}.png")
            assert rgb.shape == (360, 640, 3) and rgb.std() > 1
            if count < 3:
                if count in [0, 2]:
                    audit[name, count] = rgb
            else:
                Image.fromarray(rgb).save(out / name / f"{i:04d}.png", compress_level=1)
        errors.append(
            max(
                np.abs(matrix(path) - d["prim_world"][i, j]).max() for j, path, parent, op in replay
            )
        )
        if count == 2:
            audit_errors = {
                n: float(np.abs(audit[n, 0].astype(float) - audit[n, 2]).mean()) for n in annotators
            }
            print("SYNC_AUDIT", audit_errors, flush=True)
            assert max(audit_errors.values()) < 5, audit_errors
        if count % 20 == 0:
            print(
                "RENDER",
                i,
                len(schedule),
                "elapsed",
                round(time.perf_counter() - started, 1),
                flush=True,
            )
    verification = dict(
        source_sha256=report["source_sha256"],
        source_animation_sha256=manifest["source_sha256"],
        samples=samples,
        frames=N,
        fps=report["fps"],
        max_world_matrix_error=float(max(errors)),
        sync_audit_mae_255=audit_errors,
        wall_seconds=time.perf_counter() - started,
        front_camera_world=front.tolist(),
        ego_camera_world=d["camera_world_usd"][0].tolist(),
        max_ego_camera_transform_change=float(
            np.abs(d["camera_world_usd"] - d["camera_world_usd"][0]).max()
        ),
        camera_policy="Fixed native eye camera facing across table; fixed table-normal front camera; no hand/object tracking",
        resolution=[640, 360],
        stride=a.stride,
        light_intensity_multiplier=0.5,
        ego_focal_length_mm=ego_focal,
        front_focal_length_mm=24.0,
        native_foot_height_m=native_foot_height,
        staging="Original floor/table retained; lower-body floor penetration permitted; torso upright/table-facing",
        method="Full-scale rigid/link replay, fresh avatar geometry each sampled frame, source time retained",
    )
    (out / "verification.json").write_text(json.dumps(verification, indent=2))
    assert max(errors) < 1e-5
    print("RENDER_DONE", verification, flush=True)
finally:
    app.close()
