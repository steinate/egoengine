"""Package portable trajectories and audits; exclude large assets and rendering caches."""

import argparse, hashlib, json, zipfile
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("root", type=Path)
a = p.parse_args()
base = a.root / "task-pairs"
selected = json.loads((base / "selected.json").read_text())
out = base / "delivery"
out.mkdir(exist_ok=True)
manifest = {}
entries = []
for task, value in selected.items():
    ep = Path(value)
    v = json.loads((ep / "human/render/delivery/debug-verification.json").read_text())
    sv = json.loads((ep / "source-validation.json").read_text())
    hv = json.loads((ep / "human/validation.json").read_text())
    cv = json.loads((ep / "human/camera-verification.json").read_text())
    clearance = json.loads((ep / "human/eye-clearance.json").read_text())
    assert sv["passed"] and hv["passed"] and cv["passed"] and clearance["passed"]
    assert (
        v["source_sha256"]
        == hashlib.sha256((ep / "source/world-tracks.npz").read_bytes()).hexdigest()
    )
    assert (
        v["source_animation_sha256"]
        == hashlib.sha256((ep / "human/human-animation.npz").read_bytes()).hexdigest()
    )
    manifest[task] = {
        "episode": str(ep),
        "frames": v["frames"],
        "physics_fps": round(v["fps"]),
        "duration_s": v["frames"] / round(v["fps"]),
        "rendered_samples": len(v["samples"]),
        "source_sha256": v["source_sha256"],
        "human_sha256": v["source_animation_sha256"],
        "max_world_matrix_error": v["max_world_matrix_error"],
        "videos": v["videos"],
        "human_metrics": hv["metrics"],
        "camera_metrics": cv["metrics"],
        "eye_clearance": clearance,
        "robot_metrics": sv["metrics"],
    }
    for name in [
        "task.yaml",
        "task-provenance.json",
        "result.json",
        "source-validation.json",
        "source/world-tracks.npz",
        "source/scene-meta.json",
        "source/events.json",
        "source/resolved-task.json",
        "human/human-animation.npz",
        "human/retarget-report.json",
        "human/validation.json",
        "human/camera-verification.json",
        "human/eye-clearance.json",
        "human/render/delivery/debug-verification.json",
    ]:
        entries.append((ep / name, f"{task}/{name}"))
manifest_path = out / "pair-manifest.json"
manifest_path.write_text(json.dumps(manifest, indent=2))
entries.append((manifest_path, "pair-manifest.json"))
entries.append((base / "asset-manifest.json", "asset-manifest.json"))
archive = out / "paired-trajectories.zip"
with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for path, name in entries:
        z.write(path, name)
    z.writestr(
        "README.txt",
        "Three newly planned InternDataEngine tasks with native Worker human replay.\nAll source object/link matrices and time arrays are preserved in human-animation.npz.\nMatrices use column-vector convention, metres, and retain scale.\nphysics_step counts explicit PhysX simulate(dt) calls at 30 Hz. Raw Isaac callbacks are separate diagnostic fields.\nVideos sample at approximately 5 Hz plus contact keyframes, hold until the next source timestamp, and encode at 30 fps.\nOriginal floor/table are retained; upright human legs may penetrate the floor. Eye camera uses source robot head pitch and normalized optics. Task objects/link poses are unchanged.\nHuman contact is geometric replay, not a new dynamics simulation.\nScene USD, assets, source robot videos and frame caches remain on the server at paths in pair-manifest.json.\nSee work/task-pairs/README.md in the code repository for regeneration.\n",
    )
print(
    json.dumps(
        {
            "archive": str(archive),
            "bytes": archive.stat().st_size,
            "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            "tasks": list(manifest),
        },
        indent=2,
    )
)
