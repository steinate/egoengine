import sys, json
from pathlib import Path

ROOT = Path("/vepfs/public/pengjiaqi/interndata-human-pair")
BASE = ROOT / "human41"
OUT = BASE / "output/asset-preview"
OUT.mkdir(exist_ok=True)
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
        "anti_aliasing": 3,
    }
)
try:
    import numpy as np, omni.usd
    import omni.replicator.core as rep
    from pxr import Usd, UsdGeom, UsdSkel, UsdLux, UsdShade, Sdf, Gf
    from PIL import Image

    omni.usd.get_context().new_stage()
    stage = omni.usd.get_context().get_stage()
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    UsdGeom.SetStageUpAxis(stage, "Z")
    UsdGeom.Xform.Define(stage, "/World")
    root = UsdGeom.Xform.Define(stage, "/World/Human")
    root.AddScaleOp().Set(Gf.Vec3f(0.01))
    root.AddRotateZOp().Set(180.0)
    asset = BASE / "assets/characters/Assets/Characters/Reallusion/Worker"
    model = stage.DefinePrim("/World/Human/Model", "SkelRoot")
    model.GetReferences().AddReference(str(asset / "Props/Worker.usd"), "/Worker")
    animation = UsdSkel.Animation.Define(stage, "/World/Human/Idle")
    animation.GetPrim().GetReferences().AddReference(
        str(asset / "Motions/Worker_Idle_Pose.usd"), "/Worker/Animation"
    )
    UsdSkel.BindingAPI.Apply(
        stage.GetPrimAtPath("/World/Human/Model/Worker")
    ).CreateAnimationSourceRel().SetTargets([animation.GetPath()])
    UsdSkel.BindingAPI.Apply(model).CreateAnimationSourceRel().SetTargets([animation.GetPath()])
    from character_materials import repair_materials

    (OUT / "materials.json").write_text(json.dumps(repair_materials(stage), indent=2))
    UsdLux.DomeLight.Define(stage, "/World/Dome").CreateIntensityAttr(450.0)
    light = UsdLux.RectLight.Define(stage, "/World/Key")
    light.CreateIntensityAttr(1600.0)
    light.CreateWidthAttr(2.0)
    light.CreateHeightAttr(2.0)
    light.AddTranslateOp().Set(Gf.Vec3d(1, 2, 3))
    light.AddRotateXYZOp().Set(Gf.Vec3f(-25, 0, 20))

    def cam(path, eye, target, focal=35.0):
        eye = np.array(eye)
        z = eye - np.array(target)
        z = z / np.linalg.norm(z)
        x = np.cross([0, 0, 1], z)
        x = x / np.linalg.norm(x)
        y = np.cross(z, x)
        T = np.eye(4)
        T[:3, :3] = np.stack([x, y, z], 1)
        T[:3, 3] = eye
        c = UsdGeom.Camera.Define(stage, path)
        c.AddTransformOp().Set(Gf.Matrix4d(T.T.tolist()))
        c.CreateFocalLengthAttr(focal)
        c.CreateHorizontalApertureAttr(36.0)
        c.CreateVerticalApertureAttr(20.25)
        c.CreateClippingRangeAttr(Gf.Vec2f(0.01, 100))
        return c

    cameras = [
        ("fullbody", cam("/World/Full", [2.3, 3.0, 1.6], [0, 0, 0.95])),
        ("hands", cam("/World/Hands", [0.35, 0.9, 1.6], [-0.05, 0.27, 1.27], 55.0)),
    ]
    for name, c in cameras:
        rp = rep.create.render_product(str(c.GetPath()), (1280, 720))
        rgb = rep.AnnotatorRegistry.get_annotator("rgb")
        rgb.attach([rp])
        for _ in range(24):
            rep.orchestrator.step(rt_subframes=8, pause_timeline=True, delta_time=0.0)
        im = np.array(rgb.get_data())[..., :3]
        Image.fromarray(im).save(OUT / (name + ".png"))
        print("CAPTURE", name, float(im.std()), flush=True)
        rgb.detach([rp.path])
        rp.destroy()
    stage.Export(str(OUT / "character-scene.usda"))
    (OUT / "result.json").write_text(
        json.dumps(
            {
                "character": "Reallusion Worker CC3 sample",
                "native_skinning": True,
                "physics": False,
                "note": "Asset quality and skinning preview only; evaluation sample license.",
            },
            indent=2,
        )
    )
except BaseException:
    import traceback

    traceback.print_exc()
    raise
finally:
    app.close(wait_for_replicator=False)
