"""Audit the deployed 4.1 runtime and USD assets using its bundled Python."""

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    sys.argv = [
        sys.argv[0],
        "--allow-root",
        "--portable-root",
        str(args.output.parent / "audit-kit"),
    ]
    from omni.isaac.kit import SimulationApp

    app = SimulationApp({"headless": True, "width": 64, "height": 64, "multi_gpu": False})
    sys.path.insert(0, str(root / "runtime41/kit/exts/omni.usd.libs"))
    sys.path.insert(0, str(root / "env/curobo41-built"))
    sys.path.insert(0, str(root / "runtime41/exts/omni.isaac.ml_archive/pip_prebundle"))
    from pxr import UsdUtils
    import numpy as np
    import torch
    from curobo.wrap.reacher.motion_gen import MotionGen

    required = [
        "runtime41/python.sh",
        "run_env41.sh",
        "env/curobo41-built/curobo",
        "assets/InternDataAssets/curobo/src/curobo/curobolib/cpp",
        "robot-stack-v2/task.yaml",
        "robot-stack-v2/pipeline.yaml",
        "src/InternDataEngine41/workflows/simbox_dual_workflow.py",
        "anime-human-v1/amber-mesh.npz",
        "anime-human-v1/amber-rig.npz",
        "anime-human-v1/anime-animation.npz",
        "anime-human-v1/materials.json",
        "anime-human-v1/skin-cache/manifest.json",
        "anime-human-v1/reference/human-animation.npz",
        "human-stack-v3/source/world-tracks.npz",
        "human-stack-v3/source/source-scene.usdc",
        "human-stack-v3/source/robot-full.mp4",
    ]
    missing = [name for name in required if not (root / name).exists()]
    assert not missing, missing
    assets = {}
    for name in [
        "human-stack-v3/source/source-scene.usdc",
        "anime-human-v1/front-template.usdc",
        "anime-human-v1/ego-template.usdc",
    ]:
        layers, dependencies, unresolved = UsdUtils.ComputeAllDependencies(str(root / name))
        assets[name] = {
            "layers": [layer.realPath for layer in layers],
            "assets": dependencies,
            "unresolved": unresolved,
        }
    track = np.load(root / "human-stack-v3/source/world-tracks.npz")
    animation_path = root / "anime-human-v1/anime-animation.npz"
    animation = np.load(animation_path)
    assert all(np.array_equal(track[k], animation[k]) for k in track.files)
    distributions = sorted(
        {(d.metadata.get("Name", ""), d.version) for d in importlib.metadata.distributions()}
    )
    report = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": sys.version,
        "libc": platform.libc_ver(),
        "isaac_version": (root / "runtime41/VERSION").read_text().strip(),
        "gpu": subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"], text=True
        ).strip(),
        "torch": torch.__version__,
        "torch_cuda": torch.version.cuda,
        "cuda_available": torch.cuda.is_available(),
        "planner_import": MotionGen.__module__,
        "required_paths_present": required,
        "usd_dependencies": assets,
        "frames": len(animation["source_frame"]),
        "source_objects_bitwise_equal": True,
        "animation_sha256": hashlib.sha256(animation_path.read_bytes()).hexdigest(),
        "distributions": [{"name": n, "version": v} for n, v in distributions],
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {k: v for k, v in report.items() if k not in {"distributions", "usd_dependencies"}},
            indent=2,
        )
    )
    app.close()


if __name__ == "__main__":
    main()
