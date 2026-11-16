"""Inspect only this audit's trusted generated plans for usable rigid/link state arrays."""

import argparse
import hashlib
import json
import pickle
from pathlib import Path
import numpy as np

p = argparse.ArgumentParser()
p.add_argument("audit", type=Path)
a = p.parse_args()
reports = []
result_files = list((a.audit / "runs").glob("*/result.json")) + list(
    (a.audit / "retests").glob("*/runs/*/result.json")
)
for result in sorted(result_files):
    run = result.parent
    info = json.loads(result.read_text())
    plan = run / "official-plan.pkl"
    if info.get("status") != "planning_succeeded" or not plan.exists():
        continue
    cfg_blob, state_blob, log_blob = pickle.loads(plan.read_bytes())
    states, logger = (pickle.loads(x) for x in [state_blob, log_blob])
    n = states["num_steps"]
    paths = states.get("prim_paths", [])
    poses = states.get("prim_poses", [])
    complete = (
        states["mode"] == "prim_pose"
        and len(poses) == n == info["frames"]
        and all(len(frame) == len(paths) for frame in poses)
    )
    finite = False
    norm_error = None
    if complete and n and paths:
        xyz = np.asarray([[pose[0] for pose in frame] for frame in poses])
        quat = np.asarray([[pose[1] for pose in frame] for frame in poses])
        finite = bool(np.isfinite(xyz).all() and np.isfinite(quat).all())
        norm_error = float(np.max(np.abs(np.linalg.norm(quat, axis=-1) - 1)))
    report = dict(
        config=info["config"],
        run_dir=str(run.relative_to(a.audit)),
        mode=states["mode"],
        frames=n,
        returned_frames=info["frames"],
        prim_count=len(paths),
        complete_prim_pose_arrays=complete,
        finite=finite,
        max_quaternion_norm_error=norm_error,
        sha256=hashlib.sha256(plan.read_bytes()).hexdigest(),
        bytes=plan.stat().st_size,
        object_logger_keys=list(logger.get("object_data_logger", {}).keys()),
        object_logger_fields={
            robot: sorted(values) for robot, values in logger.get("object_data_logger", {}).items()
        },
        object_logger_frame_counts={
            robot: {key: len(value) for key, value in values.items()}
            for robot, values in logger.get("object_data_logger", {}).items()
        },
        timing_note="Official recorded-frame order. This plan schema has no independently validated physical timestamps; paired videos use the separate explicit recorder in work/task-pairs.",
        scope="Structural/state integrity only; not task success, image replay, cloth/particle completeness or human IK validation.",
    )
    (run / "plan-integrity.json").write_text(json.dumps(report, indent=2))
    reports.append(report)
(a.audit / "plan-integrity-results.json").write_text(json.dumps(reports, indent=2))
print(json.dumps(reports, indent=2))
