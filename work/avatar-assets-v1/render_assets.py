import sys, json, argparse
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--index", type=int, required=True)
a = ap.parse_args()
ROOT = Path("/vepfs/public/pengjiaqi/interndata-human-pair")
B = ROOT / "avatar-assets-v1"
spec = json.loads((B / "asset-drive-verification.json").read_text())[a.index]
name = spec["name"]
folder = Path(spec["usd"]).parent
OUT = B / "renders" / name
OUT.mkdir(exist_ok=True, parents=True)
cache = ["kit-v3-ego-part0", "kit-v3-front-part0", "kit-v3-ego-part1", "kit-v3-front-part1"][
    a.index
]
sys.argv = [
    sys.argv[0],
    "--allow-root",
    "--portable-root",
    str(ROOT / "cache41" / cache),
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
        "width": 960,
        "height": 720,
        "renderer": "RayTracedLighting",
        "anti_aliasing": 3,
    }
)
try:
    import numpy as np, omni.usd
    import omni.replicator.core as rep
    from pxr import Usd, UsdGeom, UsdLux, UsdShade, Sdf, Gf, Vt
    from PIL import Image

    omni.usd.get_context().new_stage()
    stage = omni.usd.get_context().get_stage()
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    UsdGeom.SetStageUpAxis(stage, "Z")
    UsdGeom.Xform.Define(stage, "/World")

    def look(eye, target):
        eye = np.array(eye)
        z = eye - np.array(target)
        z /= np.linalg.norm(z)
        x = np.cross([0, 0, 1], z)
        x /= np.linalg.norm(x)
        y = np.cross(z, x)
        T = np.eye(4)
        T[:3, :3] = np.stack([x, y, z], axis=1)
        T[:3, 3] = eye
        return Gf.Matrix4d(T.T.tolist())

    UsdLux.DomeLight.Define(stage, "/World/Dome").CreateIntensityAttr(350.0)
    for n, eye, power, size in [
        ("Key", [-1.0, -2.0, 3.0], 1500.0, 2.0),
        ("Fill", [1.5, -0.5, 1.8], 400.0, 2.0),
        ("Rim", [0, 1.2, 2.5], 800.0, 1.5),
    ]:
        l = UsdLux.RectLight.Define(stage, "/World/" + n)
        l.CreateIntensityAttr(power)
        l.CreateWidthAttr(size)
        l.CreateHeightAttr(size)
        l.AddTransformOp().Set(look(eye, [0, 0, 1.0]))
    floor = UsdGeom.Cube.Define(stage, "/World/Floor")
    floor.AddTranslateOp().Set(Gf.Vec3d(0, 0, -0.055))
    floor.AddScaleOp().Set(Gf.Vec3f(50, 50, 0.05))
    floor.CreateDisplayColorAttr([Gf.Vec3f(0.16, 0.18, 0.21)])
    height = spec["height_m"]
    manifest = json.loads((folder / "manifest.json").read_text())
    products = {}
    anns = {}
    for view, res, eye, target, focal, aperture in [
        ("full", (720, 960), [0.10, -3.1, 1.05], [0, 0, height * 0.5], 45.0, 24.0),
        ("hands", (960, 640), [0, -1.15, height * 0.82], [0, -0.34, height * 0.61], 45.0, 36.0),
    ]:
        c = UsdGeom.Camera.Define(stage, "/World/" + view)
        c.AddTransformOp().Set(look(eye, target))
        c.CreateFocalLengthAttr(focal)
        c.CreateHorizontalApertureAttr(aperture)
        c.CreateVerticalApertureAttr(aperture * res[1] / res[0])
        c.CreateClippingRangeAttr(Gf.Vec2f(0.015, 200.0))
        rp = rep.create.render_product(str(c.GetPath()), res)
        an = rep.AnnotatorRegistry.get_annotator("rgb")
        an.attach([rp])
        products[view] = rp
        anns[view] = an
    previous = None
    for frame in range(61):
        if previous:
            stage.RemovePrim(previous)
        path = f"/World/Model_{frame:04d}"
        p = stage.DefinePrim(path, "Xform")
        p.GetReferences().AddReference(str(folder / "visual-template.usdc"), "/Avatar")
        previous = path
        baked = np.load(folder / "cache" / f"{frame:04d}.npz")
        for j, original in enumerate(manifest["mesh_paths"]):
            m = UsdGeom.Mesh(stage.GetPrimAtPath(path + original[len("/Avatar") :]))
            m.GetPointsAttr().Set(Vt.Vec3fArray.FromNumpy(baked[f"points_{j}"]))
            m.GetNormalsAttr().Set(Vt.Vec3fArray.FromNumpy(baked[f"normals_{j}"]))
            m.SetNormalsInterpolation("vertex")
        for _ in range(40 if frame == 0 else 3):
            rep.orchestrator.step(rt_subframes=4, pause_timeline=True, delta_time=1 / 30)
        im = np.asarray(anns["hands"].get_data())[..., :3].copy()
        assert im.std() > 1
        Image.fromarray(im).save(OUT / f"{frame:04d}.png")
        if frame in [0, 30, 60]:
            Image.fromarray(np.asarray(anns["full"].get_data())[..., :3]).save(
                OUT / f"full-{frame:04d}.png"
            )
        if frame % 15 == 0:
            print("FRAME", name, frame, flush=True)
    (OUT / "render-verification.json").write_text(
        json.dumps(
            {
                "name": name,
                "frames": 61,
                "fps": 15,
                "renderer": "Isaac Sim 4.1 RTX",
                "source_usd": spec["usd"],
                "skin_method": manifest["method"],
                "purpose": spec["purpose"],
                "not_task_replay": True,
            },
            indent=2,
        )
    )
    print("ASSET_RENDER_DONE", name, flush=True)
except BaseException:
    import traceback

    traceback.print_exc()
    raise
finally:
    app.close(wait_for_replicator=False)
