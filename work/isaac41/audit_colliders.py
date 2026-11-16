"""Read authored USD geometry/physics attributes without changing simulation."""

import json
from pathlib import Path
import numpy as np
from pxr import Usd, UsdGeom

root = Path("/vepfs/public/pengjiaqi/interndata-human-pair")
assets = root / "assets/InternDataAssets/assets"
report = {}
for name, path in [
    ("franka", assets / "franka/robot.usd"),
    (
        "bottle",
        assets
        / "pick_and_place/pre-train-pick/assets/omniobject3d-bottle/google_scan-bottle_0011/Aligned_obj.usd",
    ),
]:
    stage = Usd.Stage.Open(str(path))
    rows = []
    for prim in stage.Traverse(Usd.TraverseInstanceProxies()):
        p = str(prim.GetPath())
        if name == "franka" and not any(
            k in p.lower() for k in ["finger", "panda_hand", "gripper"]
        ):
            continue
        attrs = {
            a.GetName(): a.Get()
            for a in prim.GetAttributes()
            if "Cooked" not in a.GetName()
            and any(
                k in a.GetName().lower()
                for k in ["physics", "physx", "collision", "stiffness", "damping"]
            )
        }
        row = {
            "path": p,
            "type": prim.GetTypeName(),
            "schemas": prim.GetAppliedSchemas(),
            "attributes": attrs,
        }
        if prim.IsA(UsdGeom.Mesh):
            mesh = UsdGeom.Mesh(prim)
            pts = np.array(mesh.GetPointsAttr().Get())
            mat = np.array(
                UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
            )
            row.update(
                vertices=len(pts),
                faces=len(mesh.GetFaceVertexCountsAttr().Get()),
                local_bounds=[pts.min(0).tolist(), pts.max(0).tolist()],
                world_matrix=mat.tolist(),
            )
        if attrs or prim.IsA(UsdGeom.Mesh):
            rows.append(row)
    report[name] = {
        "file": str(path),
        "meters_per_unit": UsdGeom.GetStageMetersPerUnit(stage),
        "up_axis": str(UsdGeom.GetStageUpAxis(stage)),
        "prims": rows,
    }
out = root / "outputs41/collision-audit"
out.mkdir(exist_ok=True)
(out / "authored-colliders.json").write_text(json.dumps(report, indent=2, default=str))
for name, entry in report.items():
    print(name, "meters_per_unit", entry["meters_per_unit"], "up_axis", entry["up_axis"])
    for row in entry["prims"]:
        if row["attributes"]:
            print(row["path"], row["type"], row["schemas"], row["attributes"])
