"""First-person visibility mask: retain torso/limbs, hide own face and headwear.
Observer uses the unmasked full-body template. No change to camera location.
"""

import sys, json, argparse
from pathlib import Path
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("--root", type=Path, default=Path("/vepfs/public/pengjiaqi/interndata-human-pair"))
ap.add_argument("--folder", type=Path)
args = ap.parse_args()
ROOT = args.root
BASE = args.folder or ROOT / "human-natural-v4"
sys.path.insert(0, str(ROOT / "runtime41/kit/exts/omni.usd.libs"))
from pxr import Usd, UsdGeom, Vt

s = Usd.Stage.Open(str(BASE / "skin-cache/visual-template.usdc"))
changes = []
for p in s.Traverse():
    if not p.IsA(UsdGeom.Mesh):
        continue
    m = UsdGeom.Mesh(p)
    v = np.array(m.GetPointsAttr().Get())
    name = str(p.GetPath())
    if v[:, 2].min() > 153:
        UsdGeom.Imageable(p).MakeInvisible()
        changes.append({"mesh": name, "hidden": True})
        continue
    if "CC_Base_Body" not in name:
        continue
    counts = np.array(m.GetFaceVertexCountsAttr().Get())
    ids = np.array(m.GetFaceVertexIndicesAttr().Get())
    keep = []
    corners = []
    start = 0
    for i, c in enumerate(counts):
        face = ids[start : start + c]
        if not np.any(v[face, 2] > 153):
            keep.append(i)
            corners.extend(range(start, start + c))
        start += c
    keep = np.array(keep)
    corners = np.array(corners)
    mapping = np.full(len(counts), -1)
    mapping[keep] = np.arange(len(keep))
    for pv in UsdGeom.PrimvarsAPI(m).GetPrimvars():
        if str(pv.GetInterpolation()) != "faceVarying":
            continue
        if pv.IsIndexed():
            vv = np.array(pv.GetIndices())
            pv.SetIndices(Vt.IntArray(vv[corners].tolist()))
        else:
            vals = pv.Get()
            pv.Set(type(vals)([vals[int(i)] for i in corners]))
    for subset in UsdGeom.Subset.GetAllGeomSubsets(m):
        old = np.array(subset.GetIndicesAttr().Get())
        new = mapping[old]
        subset.GetIndicesAttr().Set(Vt.IntArray(new[new >= 0].tolist()))
    m.GetFaceVertexCountsAttr().Set(Vt.IntArray(counts[keep].tolist()))
    m.GetFaceVertexIndicesAttr().Set(Vt.IntArray(ids[corners].tolist()))
    changes.append({"mesh": name, "original_faces": len(counts), "ego_faces": len(keep)})
s.Export(str(BASE / "skin-cache/ego-template.usdc"))
(BASE / "ego-visibility.json").write_text(
    json.dumps(
        {
            "method": "Hide own head/face/hat in first-person rendering; full character retained for observer rendering",
            "changes": changes,
        },
        indent=2,
    )
)
print("EGO_MASK_DONE", changes)
