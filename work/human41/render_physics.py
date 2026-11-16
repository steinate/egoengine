"""Render the saved human-contact simulation using verified baked skinning."""

import sys, json, argparse, hashlib
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--preview", action="store_true")
a = p.parse_args()
ROOT = Path("/vepfs/public/pengjiaqi/interndata-human-pair")
BASE = ROOT / "human41"
OUT = BASE / "output" / ("render-preview" if a.preview else "render-final")
OUT.mkdir(exist_ok=True)
if (OUT / "result.json").exists():
    (OUT / "result.json").unlink()
sys.argv = [
    sys.argv[0],
    "--allow-root",
    "--portable-root",
    str(ROOT / "cache41/kit"),
    f"--/log/file={OUT}/kit.log",
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
        "renderer": "RayTracedLighting",
        "anti_aliasing": 0,
    }
)
try:
    import numpy as np, omni.usd
    import omni.replicator.core as rep
    from pxr import Usd, UsdGeom, UsdLux, UsdShade, Sdf, Gf, Vt
    from PIL import Image

    cache = BASE / "output/skin-cache"
    manifest = json.loads((cache / "manifest.json").read_text())
    source = BASE / "output/physics-final/physics-tracks.npz"
    data = np.load(source)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == manifest["source_sha256"]
    assert manifest["max_usd_fk_position_error_m"] < 1e-5
    assert json.loads((BASE / "output/physics-final/result.json").read_text())["success_lift_hold"]
    camera_info = json.loads((BASE / "output/physics-final/cameras.json").read_text())
    omni.usd.get_context().new_stage()
    stage = omni.usd.get_context().get_stage()
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    UsdGeom.SetStageUpAxis(stage, "Z")
    UsdGeom.Xform.Define(stage, "/World")

    def material(path, color):
        m = UsdShade.Material.Define(stage, path)
        s = UsdShade.Shader.Define(stage, path + "/Shader")
        s.CreateIdAttr("UsdPreviewSurface")
        s.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
        s.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.55)
        m.CreateSurfaceOutput().ConnectToSource(s.ConnectableAPI(), "surface")
        return m

    wood = material("/World/Wood", (0.22, 0.16, 0.11))
    floor = material("/World/FloorMaterial", (0.2, 0.22, 0.25))
    orange = material("/World/CubeMaterial", (0.5, 0.12, 0.03))

    def box(path, position, size, mat):
        b = UsdGeom.Cube.Define(stage, path)
        b.CreateSizeAttr(1.0)
        b.AddTranslateOp().Set(Gf.Vec3d(*position))
        b.AddScaleOp().Set(Gf.Vec3f(*size))
        UsdShade.MaterialBindingAPI.Apply(b.GetPrim()).Bind(mat)
        return b

    box("/World/Table", [0, 0.55, 0.95], [1.4, 0.9, 0.1], wood)
    box("/World/Floor", [0, 0, -0.05], [5.0, 5.0, 0.1], floor)
    for k, (x, y) in enumerate([(-0.6, 0.2), (0.6, 0.2), (-0.6, 0.9), (0.6, 0.9)]):
        box("/World/Leg" + str(k), [x, y, 0.45], [0.07, 0.07, 0.9], wood)
    cube = UsdGeom.Cube.Define(stage, "/World/Cube")
    cube.CreateSizeAttr(0.06)
    cube_t = cube.AddTranslateOp()
    cube_q = cube.AddOrientOp(UsdGeom.XformOp.PrecisionDouble)
    UsdShade.MaterialBindingAPI.Apply(cube.GetPrim()).Bind(orange)
    root = UsdGeom.Xform.Define(stage, "/World/Human")
    root.AddScaleOp().Set(Gf.Vec3f(0.01))
    root.AddRotateZOp().Set(180.0)
    UsdLux.DomeLight.Define(stage, "/World/Dome").CreateIntensityAttr(700.0)
    key = UsdLux.RectLight.Define(stage, "/World/Key")
    key.CreateIntensityAttr(1300.0)
    key.CreateWidthAttr(2.0)
    key.CreateHeightAttr(2.0)
    key.AddTranslateOp().Set(Gf.Vec3d(0.6, 0.5, 3.0))
    annotators = {}
    products = []
    for name, cfg in camera_info.items():
        c = UsdGeom.Camera.Define(stage, "/World/" + name)
        T = np.array(cfg["T_world_camera_opencv"]) @ np.diag([1.0, -1.0, -1.0, 1.0])
        c.AddTransformOp().Set(Gf.Matrix4d(T.T.tolist()))
        c.CreateFocalLengthAttr(cfg["K"][0][0] / 1280 * 36)
        c.CreateHorizontalApertureAttr(36.0)
        c.CreateVerticalApertureAttr(20.25)
        c.CreateClippingRangeAttr(Gf.Vec2f(0.18 if name == "ego" else 0.025, 100.0))
        rp = rep.create.render_product(str(c.GetPath()), (1280, 720))
        an = rep.AnnotatorRegistry.get_annotator("rgb")
        an.attach([rp])
        annotators[name] = an
        products.append(rp)
        (OUT / name).mkdir(exist_ok=True)
    samples = [0, 90, 150, 240] if a.preview else manifest["samples"]
    previous = None
    errors = []
    for frame, sample in enumerate(samples):
        if previous is not None:
            stage.RemovePrim(previous)
        path = f"/World/Human/Frame_{sample:04d}"
        avatar = stage.DefinePrim(path, "Xform")
        avatar.GetReferences().AddReference(str(cache / "visual-template.usdc"), "/Worker")
        baked = np.load(cache / f"{sample:04d}.npz")
        for j, original in enumerate(manifest["mesh_paths"]):
            mesh = UsdGeom.Mesh(stage.GetPrimAtPath(path + original[len("/Worker") :]))
            mesh.GetPointsAttr().Set(Vt.Vec3fArray.FromNumpy(baked[f"points_{j}"]))
            mesh.GetNormalsAttr().Set(Vt.Vec3fArray.FromNumpy(baked[f"normals_{j}"]))
            mesh.SetNormalsInterpolation("vertex")
        previous = path
        cube_t.Set(Gf.Vec3d(*map(float, data["cube_position_m"][sample])))
        q = data["cube_quaternion_wxyz"][sample]
        cube_q.Set(Gf.Quatd(float(q[0]), Gf.Vec3d(*map(float, q[1:]))))
        for _ in range(4 if frame == 0 else 3):
            rep.orchestrator.step(rt_subframes=3, pause_timeline=True, delta_time=1 / 30)
        for name, an in annotators.items():
            im = np.asarray(an.get_data())[..., :3].copy()
            assert im.shape == (720, 1280, 3) and im.std() > 1
            Image.fromarray(im).save(OUT / name / f"{frame:04d}.png")
        got = np.array(
            UsdGeom.Xformable(cube.GetPrim()).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
        ).T
        errors.append(float(np.linalg.norm(got[:3, 3] - data["cube_position_m"][sample])))
        if frame % 15 == 0 or a.preview:
            print(
                "RENDERED", frame, "source_sample", sample, "cube_z", float(got[2, 3]), flush=True
            )
    (OUT / "result.json").write_text(
        json.dumps(
            {
                "frames": len(samples),
                "fps": 15,
                "source_samples": samples,
                "source_physics_sha256": manifest["source_sha256"],
                "max_cube_replay_position_error_m": max(errors),
                "max_skinning_joint_position_error_m": manifest["max_usd_fk_position_error_m"],
                "renderer": "Isaac Sim 4.1 RTX",
                "method": "offline rendering of saved human-contact dynamics; original rigged asset CPU-skinned and recreated per sample to avoid stale skinning buffers",
                "object_physics_simulated_before_rendering": True,
                "source_physics_result": json.loads(
                    (BASE / "output/physics-final/result.json").read_text()
                ),
            },
            indent=2,
        )
    )
    print("RENDER_DONE", len(samples), flush=True)
except BaseException:
    import traceback

    traceback.print_exc()
    raise
finally:
    app.close(wait_for_replicator=False)
