"""Evaluate source mesh vertices using the recorded world transforms, including scale."""

import numpy as np
from pxr import Usd, UsdGeom


def object_meshes(stage, meta, path):
    result = []
    for pr in Usd.PrimRange(stage.GetPrimAtPath(path)):
        if not pr.IsA(UsdGeom.Mesh):
            continue
        v = np.asarray(UsdGeom.Mesh(pr).GetPointsAttr().Get())
        if not len(v):
            continue
        ancestor = max(
            [
                x
                for x in meta["prim_paths"]
                if str(pr.GetPath()).startswith(x + "/") or str(pr.GetPath()) == x
            ],
            key=len,
        )
        A = np.asarray(
            UsdGeom.Xformable(stage.GetPrimAtPath(ancestor)).ComputeLocalToWorldTransform(
                Usd.TimeCode.Default()
            )
        ).T
        M = np.asarray(UsdGeom.Xformable(pr).ComputeLocalToWorldTransform(Usd.TimeCode.Default())).T
        rel = np.linalg.inv(A) @ M
        result.append((meta["prim_paths"].index(ancestor), v @ rel[:3, :3].T + rel[:3, 3]))
    assert result, path
    return result


def bounds(meshes, prim_world):
    points = np.concatenate([v @ prim_world[j, :3, :3].T + prim_world[j, :3, 3] for j, v in meshes])
    return points.min(0), points.max(0)
