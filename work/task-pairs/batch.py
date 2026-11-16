"""Bounded sequential official planning retries; preserve every failed trial."""

import argparse, json, subprocess
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("workspace", type=Path)
p.add_argument("--tasks", nargs="+", default=["hang_cup", "close_microwave", "insert_flower"])
p.add_argument("--seeds", nargs="+", type=int, default=[43, 44, 42])
p.add_argument("--tag", default="")
a = p.parse_args()
w = a.workspace.resolve()
root = w / "run"
code = root / "task-pairs"
selected = (
    json.loads((code / "selected.json").read_text()) if (code / "selected.json").exists() else {}
)
for task in a.tasks:
    for seed in a.seeds:
        ep = code / task / (f"seed-{seed}" + ("-" + a.tag if a.tag else ""))
        if not (ep / "result.json").exists():
            subprocess.run(
                [
                    "bash",
                    str(root / "human41/usd_python.sh"),
                    str(code / "prepare.py"),
                    str(root),
                    str(w / "egoengine"),
                    task,
                    "--seed",
                    str(seed),
                    "--tag",
                    a.tag,
                ],
                check=True,
                cwd=w,
            )
            with (w / f"logs/pair-{task}-{seed}-{a.tag}.log").open("w") as log:
                subprocess.run(
                    ["bash", str(root / "run_env41.sh"), str(code / "robot.py"), str(ep)],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    cwd=w,
                )
        if (ep / "result.json").exists():
            r = json.loads((ep / "result.json").read_text())
            print("TRIAL", task, seed, r, flush=True)
            if r["official_success"] and r["cadence_valid"]:
                validation = subprocess.run(
                    [
                        "bash",
                        str(root / "human41/usd_python.sh"),
                        str(code / "validate.py"),
                        str(ep),
                    ],
                    cwd=w,
                )
                if validation.returncode == 0:
                    selected[task] = str(ep)
                    break
    temporary = code / "selected.json.tmp"
    temporary.write_text(json.dumps(selected, indent=2))
    temporary.replace(code / "selected.json")
print("BATCH_DONE", selected, flush=True)
