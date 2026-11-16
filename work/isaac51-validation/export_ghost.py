"""Export GHOST surfels as thin volumetric Gaussians for a compatibility experiment.
This is an approximation, not an exact 2DGS-to-3DGS conversion.
"""

import sys, json, types, argparse
from pathlib import Path

ROOT = Path("/vepfs/public/pengjiaqi/interndata-human-pair")
GS = ROOT / "gaussian-ego"
OUT = ROOT / "validation51/output/ghost-reference"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(GS))
from ghost_adapter import avatar, camera, np, torch
from gaussian_renderer import render
from PIL import Image

g = avatar()
g.active_sh_degree = 0
motion = dict(np.load(GS / "output/motion.npz"))
cfg = json.loads((GS / "output/camera.json").read_text())
T = np.array(cfg["T_world_camera_opencv"])
K = np.array(cfg["K"])
cam = camera(T, K, 960, 540)
pipe = types.SimpleNamespace(
    debug=False, compute_cov3D_python=False, convert_SHs_python=False, depth_ratio=1.0
)
p = argparse.ArgumentParser()
p.add_argument("--all", action="store_true")
args = p.parse_args()
ids = list(range(0, 91, 3)) if args.all else [0, 30, 60, 90]
for k in ids:
    with torch.no_grad():
        g.update_mesh_properties(
            torch.tensor(motion["vertices"][k][None], device="cuda", dtype=torch.float32),
            g.canonical_verts[None],
        )
        # Use the original renderer and SH degree 0, matching the published viewer default.
        r = render(cam, g, pipe, torch.zeros(3, device="cuda"))
        col = r["render"].cpu().numpy().transpose(1, 2, 0)
        alpha = r["rend_alpha"].cpu().numpy()[0]
        Image.fromarray(np.uint8(np.clip(col, 0, 1) * 255)).save(OUT / f"{k:04d}.png")
        np.save(OUT / f"{k:04d}-alpha.npy", alpha)
        scales = g.get_scaling.cpu().numpy()
        assert scales.shape[1] == 2
        scales = np.column_stack([scales, np.full(len(scales), 0.0001)])
        rot = g.get_gaussians_rotation().cpu().numpy()
        rot /= np.linalg.norm(rot, axis=1, keepdims=True)
        np.savez(
            OUT / f"{k:04d}.npz",
            positions=g.get_gaussians_position().cpu().numpy(),
            rotations=rot,
            scales=np.log(scales),
            densities=g._opacity.cpu().numpy(),
            features_albedo=g.get_features[:, 0, :].cpu().numpy(),
            features_specular=np.zeros((len(scales), 0), dtype=np.float32),
        )
        print("EXPORTED_GHOST", k, flush=True)
(OUT / "camera.json").write_text(json.dumps(cfg, indent=2))
(OUT / "manifest.json").write_text(
    json.dumps(
        {
            "source": "GHOST pretrained avatar",
            "representation": "2D surfels approximated by 3D Gaussians with 0.1 mm third standard deviation",
            "sh_degree": 0,
            "reference_renderer": "original GHOST diff-surfel-rasterization; no compositing; black background",
            "frames": ids,
            "source_frames": motion["source_frames"][ids].tolist(),
            "gaussians": len(scales),
        },
        indent=2,
    )
)
