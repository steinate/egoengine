"""Headless adapter to GHOST's published avatar and renderer, no training pipeline."""

import sys, types, inspect
from pathlib import Path
import numpy as np
import torch

HERE = Path(__file__).resolve().parent
REPO = HERE / "GHOST"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "submodules/manopth"))
# Avoid importing dataset reconstruction dependencies for the avatar-only use.
scene = types.ModuleType("scene")
scene.__path__ = [str(REPO / "scene")]
sys.modules["scene"] = scene
if not hasattr(inspect, "getargspec"):
    inspect.getargspec = inspect.getfullargspec
for name, value in [
    ("bool", np.bool_),
    ("int", int),
    ("float", float),
    ("complex", complex),
    ("object", object),
    ("str", str),
    ("unicode", str),
]:
    setattr(np, name, value)
from gaussian_renderer import GaussianModelManoHybrid, render
from utils.graphics_utils import getProjectionMatrix
from utils.sh_utils import eval_sh


def avatar():
    g = GaussianModelManoHybrid(3)
    g.load_ply(REPO / "data/point_cloud.ply")
    g.select_mesh_by_timestep(0)
    return g


def camera(T, K, width, height):
    """T is world-from-camera with OpenCV right/down/forward axes."""
    fovx = 2 * np.arctan(width / (2 * K[0, 0]))
    fovy = 2 * np.arctan(height / (2 * K[1, 1]))
    view = torch.tensor(np.linalg.inv(T).T, dtype=torch.float32, device="cuda")
    proj = getProjectionMatrix(0.01, 100.0, fovx, fovy).cuda().T
    return types.SimpleNamespace(
        FoVx=fovx,
        FoVy=fovy,
        image_width=width,
        image_height=height,
        world_view_transform=view,
        projection_matrix=proj,
        full_proj_transform=view @ proj,
        camera_center=torch.tensor(T[:3, 3], device="cuda", dtype=torch.float32),
        znear=0.01,
        zfar=100.0,
    )


def capture(g, cam, scene_depth=None):
    pipe = types.SimpleNamespace(
        debug=False, compute_cov3D_python=False, convert_SHs_python=False, depth_ratio=1.0
    )
    bg = torch.zeros(3, device="cuda")
    if scene_depth is not None:
        depth = torch.as_tensor(scene_depth, dtype=torch.float32, device="cuda").flatten()
        bg = torch.cat([torch.tensor([-1.0, 0, 0], device="cuda"), depth]).contiguous()
    with torch.no_grad():
        # Transport the view direction into each canonical face's frame, preserving
        # the pretrained degree-3 directional appearance under skeletal deformation.
        direction = g.get_gaussians_position() - cam.camera_center
        direction = torch.linalg.solve(g.transforms_image[:, :3, :3], direction[:, :, None])[
            :, :, 0
        ]
        direction = direction / direction.norm(dim=-1, keepdim=True).clamp_min(1e-8)
        colors = (eval_sh(3, g.get_features.transpose(1, 2), direction) + 0.5).clamp_min(0)
        return render(cam, g, pipe, bg, override_color=colors)


if __name__ == "__main__":
    import imageio.v2 as iio, json

    out = HERE / "output"
    out.mkdir(exist_ok=True)
    g = avatar()
    v = g.canonical_verts.detach().cpu().numpy()
    p = g.get_xyz.detach().cpu().numpy()
    np.savez(
        out / "canonical.npz",
        vertices=v,
        faces=g.faces.cpu().numpy(),
        joints=g.mano_layer(g.pose_param, g.shape_param, g.transl)[1].detach().cpu().numpy() / 1000,
    )
    center = (v.min(0) + v.max(0)) / 2
    for sign in [-1, 1]:
        eye = center + np.array([0, 0, sign * 0.35])
        z = center - eye
        z /= np.linalg.norm(z)
        x = np.cross(z, [0, 1, 0])
        x /= np.linalg.norm(x)
        y = np.cross(z, x)
        T = np.eye(4)
        T[:3, :3] = np.stack([x, y, z], 1)
        T[:3, 3] = eye
        r = capture(g, camera(T, np.array([[650, 0, 320], [0, 650, 240], [0, 0, 1]]), 640, 480))
        rgb = r["render"].detach().cpu().numpy().transpose(1, 2, 0)
        alpha = r["rend_alpha"].detach().cpu().numpy().transpose(1, 2, 0)
        iio.imwrite(
            out / f"official-hand-{sign}.png",
            np.uint8(np.clip(rgb + (1 - alpha) * 0.8, 0, 1) * 255),
        )
    print(
        "GHOST_SMOKE_OK",
        len(p),
        "bounds",
        v.min(0),
        v.max(0),
        "gaussian bounds",
        p.min(0),
        p.max(0),
        flush=True,
    )
