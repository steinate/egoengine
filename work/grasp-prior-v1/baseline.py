"""Freeze a successful episode and reject changes to source state, camera, or timing."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import numpy as np


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_arrays(source_path, baseline_path, candidate_path):
    checks = {}
    with (
        np.load(source_path, allow_pickle=False) as source,
        np.load(baseline_path, allow_pickle=False) as baseline,
        np.load(candidate_path, allow_pickle=False) as candidate,
    ):
        for key in source.files:
            checks[f"source/{key}"] = (
                key in candidate
                and np.array_equal(source[key], candidate[key])
                and np.array_equal(source[key], baseline[key])
            )
        for key in [
            "camera_world_usd",
            "world_transform",
            "source_frame",
            "video_time_s",
            "names",
            "parents",
        ]:
            checks[f"baseline/{key}"] = key in candidate and np.array_equal(
                baseline[key], candidate[key]
            )
        checks["pose_shape"] = candidate["local"].shape == baseline["local"].shape
        checks["pose_finite"] = bool(np.isfinite(candidate["local"]).all())
        # Preserve the native eye attachment as well as the camera matrix.
        names = [str(n).split("/")[-1] for n in baseline["names"]]
        locked = set()
        for name in ["L_Eye", "R_Eye"]:
            i = names.index(name)
            while i >= 0:
                locked.add(i)
                i = int(baseline["parents"][i])
        checks["native_eye_chain_unchanged"] = np.array_equal(
            baseline["local"][:, sorted(locked)], candidate["local"][:, sorted(locked)]
        )
    return {"passed": all(checks.values()), "checks": checks}


def freeze(episode, destination, include_videos=True):
    paths = [
        "source/world-tracks.npz",
        "source/events.json",
        "source/scene-meta.json",
        "source-validation.json",
        "task-provenance.json",
        "human/human-animation.npz",
        "human/retarget-report.json",
        "human/validation.json",
        "human/camera-verification.json",
        "human/render/delivery/debug-verification.json",
    ]
    if include_videos:
        paths += [
            f"human/render/delivery/{name}.mp4"
            for name in ["human-ego-debug", "robot-ego-front-debug"]
        ]
    for name in [
        "source-validation.json",
        "human/validation.json",
        "human/camera-verification.json",
    ]:
        if not json.loads((episode / name).read_text())["passed"]:
            raise ValueError(f"Baseline has not passed: {name}")
    report = validate_arrays(
        episode / "source/world-tracks.npz",
        episode / "human/human-animation.npz",
        episode / "human/human-animation.npz",
    )
    if not report["passed"]:
        raise ValueError(report)
    files = {name: digest(episode / name) for name in paths}
    camera = json.loads((episode / "human/render/delivery/debug-verification.json").read_text())
    manifest = {
        "episode": str(episode),
        "files": files,
        "render_lock": {
            k: camera[k]
            for k in [
                "front_camera_world",
                "ego_camera_world",
                "ego_focal_length_mm",
                "front_focal_length_mm",
                "resolution",
                "samples",
                "frames",
                "fps",
            ]
        },
        "validation": report,
    }
    destination.mkdir(parents=True, exist_ok=False)
    for name in paths:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(episode / name, target)
        target.chmod(0o444)
    path = destination / "baseline-lock.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    path.chmod(0o444)
    return manifest


def check(baseline, candidate_folder, render_report=None):
    manifest = json.loads((baseline / "baseline-lock.json").read_text())
    result = validate_arrays(
        baseline / "source/world-tracks.npz",
        baseline / "human/human-animation.npz",
        candidate_folder / "human-animation.npz",
    )
    checks = result["checks"]
    checks["baseline_files_untouched"] = all(
        digest(baseline / name) == expected for name, expected in manifest["files"].items()
    )
    if render_report:
        actual = json.loads(render_report.read_text())
        for key, expected in manifest["render_lock"].items():
            checks[f"render/{key}"] = key in actual and actual[key] == expected
        checks["render_animation_hash"] = actual.get("source_animation_sha256") == digest(
            candidate_folder / "human-animation.npz"
        )
    result["passed"] = all(checks.values())
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="mode", required=True)
    f = sub.add_parser("freeze")
    f.add_argument("episode", type=Path)
    f.add_argument("destination", type=Path)
    f.add_argument("--without-videos", action="store_true")
    c = sub.add_parser("check")
    c.add_argument("baseline", type=Path)
    c.add_argument("candidate_folder", type=Path)
    c.add_argument("--render-report", type=Path)
    a = p.parse_args()
    if a.mode == "freeze":
        result = freeze(a.episode.resolve(), a.destination.resolve(), not a.without_videos)
    else:
        result = check(a.baseline.resolve(), a.candidate_folder.resolve(), a.render_report)
        if not result["passed"]:
            print(json.dumps(result, indent=2))
            raise SystemExit(1)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
