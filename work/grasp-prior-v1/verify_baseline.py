"""Exercise pairing locks using existing real episode archives, including corruptions."""

import argparse
import json
from pathlib import Path
import tempfile
import zipfile
import numpy as np
from baseline import freeze, check


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive", type=Path)
    p.add_argument("work", type=Path)
    a = p.parse_args()
    a.work.mkdir(parents=True, exist_ok=True)
    reports = {}
    with tempfile.TemporaryDirectory(dir=a.work) as td, zipfile.ZipFile(a.archive) as archive:
        tmp = Path(td)
        for task in ["hang_cup", "insert_flower"]:
            episode = tmp / task
            for member in archive.namelist():
                if not member.startswith(task + "/"):
                    continue
                relative = Path(member)
                if relative.is_absolute() or ".." in relative.parts:
                    raise ValueError("Unsafe archive member")
                target = tmp / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(member))
            baseline = tmp / (task + "-baseline")
            freeze(episode, baseline, include_videos=False)
            candidate = tmp / (task + "-candidate")
            candidate.mkdir()
            with np.load(episode / "human/human-animation.npz", allow_pickle=False) as original:
                data = {k: original[k] for k in original.files}

            def run(changes):
                state = {k: v.copy() for k, v in data.items()}
                changes(state)
                np.savez_compressed(candidate / "human-animation.npz", **state)
                return check(baseline, candidate)["passed"]

            tests = {"original_accepted": run(lambda d: None)}

            def shift_camera(d):
                d["camera_world_usd"][0, 0, 3] += 0.001

            def shift_time(d):
                d["video_time_s"][1] += 0.001

            def shift_object(d):
                d["prim_world"][1, 0, 0, 3] += 0.001

            def shift_head(d):
                names = [str(n).split("/")[-1] for n in d["names"]]
                d["local"][0, names.index("Head"), 0, 3] += 0.001

            for name, mutation in [
                ("camera", shift_camera),
                ("time", shift_time),
                ("object", shift_object),
                ("head", shift_head),
            ]:
                tests[name + "_change_rejected"] = not run(mutation)

            def move_arm(d):
                names = [str(n).split("/")[-1] for n in d["names"]]
                # Pairing invariant permits arm changes; grasp quality is a separate gate.
                angle = 0.01
                R = np.array(
                    [
                        [1, 0, 0],
                        [0, np.cos(angle), -np.sin(angle)],
                        [0, np.sin(angle), np.cos(angle)],
                    ]
                )
                d["local"][0, names.index("L_Forearm"), :3, :3] @= R

            tests["arm_change_allowed_by_pairing_lock"] = run(move_arm)
            if not all(tests.values()):
                raise AssertionError(tests)
            reports[task] = tests
    report = {
        "passed": True,
        "tasks": reports,
        "scope": "Pairing locks only; no neural model or new grasp has been run.",
    }
    (a.work / "baseline-test.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
