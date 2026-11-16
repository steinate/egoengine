import sys, json
from pathlib import Path

ROOT = Path("/vepfs/public/pengjiaqi/interndata-human-pair")
sys.path.insert(0, str(ROOT / "runtime41/kit/exts/omni.usd.libs"))
from pxr import Usd, UsdSkel, UsdGeom
import numpy as np

BASE = ROOT / "human41"
asset = BASE / "assets/characters/Assets/Characters/Reallusion/Worker/Props/Worker.usd"
s = Usd.Stage.Open(str(asset))
report = {
    "asset": str(asset),
    "meters_per_unit": UsdGeom.GetStageMetersPerUnit(s),
    "up_axis": str(UsdGeom.GetStageUpAxis(s)),
    "roots": [(str(p.GetPath()), p.GetTypeName()) for p in s.GetPseudoRoot().GetChildren()],
    "skeletons": [],
    "meshes": [],
}
for p in s.Traverse():
    if p.IsA(UsdSkel.Skeleton):
        sk = UsdSkel.Skeleton(p)
        names = list(sk.GetJointsAttr().Get())
        rest = np.array(sk.GetRestTransformsAttr().Get())
        bind = np.array(sk.GetBindTransformsAttr().Get())
        xf = np.array(UsdGeom.Xformable(p).ComputeLocalToWorldTransform(Usd.TimeCode.Default()))
        report["skeletons"].append(
            {
                "path": str(p.GetPath()),
                "names": names,
                "world_transform": xf.tolist(),
                "animation": list(
                    map(str, UsdSkel.BindingAPI(p).GetAnimationSourceRel().GetTargets())
                ),
            }
        )
        np.savez(
            BASE / "output/worker-skeleton.npz",
            names=names,
            rest=rest,
            bind=bind,
            world_transform=xf,
            meters_per_unit=UsdGeom.GetStageMetersPerUnit(s),
        )
    if p.IsA(UsdGeom.Mesh):
        m = UsdGeom.Mesh(p)
        report["meshes"].append(
            {
                "path": str(p.GetPath()),
                "vertices": len(m.GetPointsAttr().Get()),
                "faces": len(m.GetFaceVertexCountsAttr().Get()),
                "skel": list(map(str, UsdSkel.BindingAPI(p).GetSkeletonRel().GetTargets())),
            }
        )
(BASE / "output/worker-inspection.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
