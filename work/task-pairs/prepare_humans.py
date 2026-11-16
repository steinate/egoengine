"""CPU preparation of the selected episodes while the next robot task runs."""

import argparse, json, subprocess, time
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("workspace", type=Path)
p.add_argument("--planner-pid", type=int, required=True)
a = p.parse_args()
w = a.workspace.resolve()
root = w / "run"
code = root / "task-pairs"
seen = set()
while True:
    selected = (
        json.loads((code / "selected.json").read_text())
        if (code / "selected.json").exists()
        else {}
    )
    for task, value in selected.items():
        ep = Path(value)
        if value in seen:
            continue
        seen.add(value)
        commands = [
            ["validate.py", str(ep)],
            [
                "human.py",
                str(root),
                str(ep),
                *(["--grasp-roll", "-20"] if task == "insert_flower" else []),
            ],
            *([["refine_fingers.py", str(root), str(ep)]] if task == "insert_flower" else []),
            [
                "gaze.py",
                str(root),
                str(ep),
                *(["--follow-object"] if task == "insert_flower" else []),
            ],
            ["check_human.py", str(ep)],
            ["bake.py", "--root", str(root), "--folder", str(ep / "human"), "--stride", "3"],
            ["ego_mask.py", "--root", str(root), "--folder", str(ep / "human")],
        ]
        with (w / f"logs/pair-{task}-{ep.name}-human.log").open("w") as log:
            for script, *args in commands:
                r = subprocess.run(
                    ["bash", str(root / "human41/usd_python.sh"), str(code / script), *args],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    cwd=w,
                )
                if r.returncode:
                    print("HUMAN_PREP_FAILED", task, script, r.returncode, flush=True)
                    break
            else:
                print("HUMAN_PREP_READY", task, ep, flush=True)
    if not Path(f"/proc/{a.planner_pid}").exists():
        break
    time.sleep(5)
