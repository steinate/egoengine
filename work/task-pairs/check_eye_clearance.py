"""Check the eye/near plane against visible avatar triangle surfaces at rendered samples."""

import argparse
import json
from pathlib import Path
import numpy as np
from pxr import Usd, UsdGeom

p = argparse.ArgumentParser()
p.add_argument("episode", type=Path)
a = p.parse_args()
folder = a.episode / "human"
d = np.load(folder / "human-animation.npz")
cache = folder / "skin-cache"
manifest = json.loads((cache / "manifest.json").read_text())
stage = Usd.Stage.Open(str(cache / "ego-template.usdc"))
triangles = {}
for j, path in enumerate(manifest["mesh_paths"]):
    mesh = UsdGeom.Mesh(stage.GetPrimAtPath(path))
    if mesh.ComputeVisibility() == UsdGeom.Tokens.invisible:
        continue
    ids = np.asarray(mesh.GetFaceVertexIndicesAttr().Get())
    faces, offset = [], 0
    for count in mesh.GetFaceVertexCountsAttr().Get():
        face = ids[offset : offset + count]
        faces.extend([face[0], face[k], face[k + 1]] for k in range(1, count - 1))
        offset += count
    triangles[j] = np.asarray(faces)


def surface_distance(points, faces, eye):
    A, B, C = (points[faces[:, i]] for i in range(3))
    ab, ac, ap = B - A, C - A, eye - A
    dot = lambda u, v: np.einsum("ij,ij->i", u, v)
    aa, bb, cc = dot(ab, ab), dot(ab, ac), dot(ac, ac)
    denominator = aa * cc - bb * bb
    u = (cc * dot(ap, ab) - bb * dot(ap, ac)) / np.maximum(denominator, 1e-20)
    v = (aa * dot(ap, ac) - bb * dot(ap, ab)) / np.maximum(denominator, 1e-20)
    normal = np.cross(ab, ac)
    normal_length = np.linalg.norm(normal, axis=1)
    plane = np.abs(dot(ap, normal)) / np.maximum(normal_length, 1e-20)
    inside = (u >= 0) & (v >= 0) & (u + v <= 1) & (denominator > 1e-15)
    distance = np.where(inside, plane, np.inf)
    for P, Q in [(A, B), (B, C), (C, A)]:
        edge = Q - P
        t = np.clip(dot(eye - P, edge) / np.maximum(dot(edge, edge), 1e-20), 0, 1)
        distance = np.minimum(distance, np.linalg.norm(eye - (P + t[:, None] * edge), axis=1))
    return float(distance.min()) * 0.01


minimum = (float("inf"), None, None)
inverse = np.linalg.inv(d["world_transform"])
for frame in manifest["samples"]:
    eye = (inverse @ np.r_[d["camera_world_usd"][frame, :3, 3], 1])[:3] * 100
    with np.load(cache / f"{frame:04d}.npz") as baked:
        for j, faces in triangles.items():
            value = surface_distance(baked[f"points_{j}"], faces, eye)
            if value < minimum[0]:
                minimum = (value, frame, manifest["mesh_paths"][j])
report = dict(
    passed=minimum[0] > 0.045,
    min_visible_avatar_surface_distance_m=minimum[0],
    near_clip_m=0.045,
    nearest_frame=minimum[1],
    nearest_mesh=minimum[2],
    checked_samples=len(manifest["samples"]),
    scope="Eye-to-visible-avatar triangle clearance at baked samples. Own head is masked only in ego; observer retains it. This is not a whole-body collision proof.",
)
(folder / "eye-clearance.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
assert report["passed"], report
