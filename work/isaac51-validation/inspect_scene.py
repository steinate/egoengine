import sys, glob, json

sys.path.insert(0, glob.glob("/isaac-sim/extscache/omni.usd.libs-*")[0])
from pxr import Usd, UsdGeom

s = Usd.Stage.Open(
    "/vepfs/public/pengjiaqi/interndata-human-pair/outputs41/human-ego/source-scene.usdc"
)
print("METADATA", s.GetPseudoRoot().GetAllMetadata())
print("ROOTS", [(str(p.GetPath()), p.GetTypeName()) for p in s.GetPseudoRoot().GetChildren()])
print(
    "GRAPHS",
    [(str(p.GetPath()), p.GetTypeName()) for p in s.Traverse() if "Graph" in p.GetTypeName()],
)
n = 0
for p in s.Traverse():
    if p.GetTypeName() in ["DomeLight", "Shader"]:
        print(
            str(p.GetPath()),
            p.GetTypeName(),
            {
                a.GetName(): str(a.Get())[:250]
                for a in p.GetAttributes()
                if a.HasAuthoredValueOpinion()
            },
        )
        n += 1
        if n >= 8:
            break
print(
    "CACHED_ATTRS",
    sum(a.GetName().startswith("omni:rtx") for p in s.Traverse() for a in p.GetAttributes()),
)
for p in s.Traverse():
    if p.GetTypeName() == "Mesh" and "/table/" in str(p.GetPath()):
        mesh = UsdGeom.Mesh(p)
        print(
            "MESH_NORMALS",
            str(p.GetPath()),
            "vertices",
            len(mesh.GetPointsAttr().Get()),
            "corners",
            len(mesh.GetFaceVertexIndicesAttr().Get()),
            [
                (
                    a.GetName(),
                    len(a.Get()) if hasattr(a.Get(), "__len__") else str(a.Get()),
                    a.GetMetadata("interpolation"),
                )
                for a in p.GetAttributes()
                if "normal" in a.GetName().lower()
            ],
        )
        break
for p in s.Traverse():
    for a in p.GetAttributes():
        if a.HasAuthoredValueOpinion() and any(
            v in a.GetName().lower()
            for v in [
                "matte",
                "visibility",
                "lightlist",
                "exposure",
                "purpose",
                "lightlink",
                "enable",
            ]
        ):
            print("SPECIAL", str(p.GetPath()), a.GetName(), str(a.Get())[:120])
