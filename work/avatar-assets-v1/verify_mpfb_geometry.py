import sys, json, re, numpy as np
from pathlib import Path

sys.path.insert(0, "/vepfs/public/pengjiaqi/interndata-human-pair/runtime41/kit/exts/omni.usd.libs")
from pxr import Usd, UsdGeom

B = Path("/vepfs/public/pengjiaqi/interndata-human-pair/avatar-assets-v1")
s = Usd.Stage.Open(str(B / "usd/mpfb_cc0_adult_male/visual-template.usdc"))
m = json.loads((B / "usd/mpfb_cc0_adult_male/manifest.json").read_text())
ref = np.load(B / "blender-mesh-reference.npz")
stats = json.loads((B / "blender-mesh-reference.json").read_text())
report = {}
for frame in [0, 30, 60]:
    b = np.load(B / f"usd/mpfb_cc0_adult_male/cache/{frame:04d}.npz")
    row = {}
    for i, p in enumerate(m["mesh_paths"]):
        name = p.split("/")[-2]
        ob = next(x for x in stats if re.sub("[^a-zA-Z0-9_]", "_", x["object"]) == name)
        v = b[f"points_{i}"]
        W = np.array(UsdGeom.Xformable(s.GetPrimAtPath(p)).ComputeLocalToWorldTransform(frame))
        v = (np.c_[v, np.ones(len(v))] @ W)[:, :3]
        bv = ref[str(frame) + "_" + ob["object"]]
        assert v.shape == bv.shape
        error = float(np.linalg.norm(v - bv, axis=1).max())
        assert error < 1e-5, (frame, name, error)
        row[ob["object"]] = error
    report[str(frame)] = row
(B / "mpfb-usd-mesh-verification.json").write_text(json.dumps(report, indent=2))
print("GEOMETRY_MATCH", max(e for row in report.values() for e in row.values()), flush=True)
