"""Run every preflight-ready config once; record blocked configs and per-run timeouts separately."""

import argparse, hashlib, json, os, signal, subprocess, time, fcntl
from pathlib import Path
from process_control import terminate_group

p = argparse.ArgumentParser()
p.add_argument("workspace", type=Path)
p.add_argument("--timeout", type=int, default=240)
a = p.parse_args()
w = a.workspace
r = w / "run"
base = r / "task-audit"
repo = w / "egoengine"
rows = json.loads((base / "inventory.json").read_text())["rows"]
summary = []
for index, row in enumerate(rows):
    item = dict(config=row["config"], family=row["family"], preflight=row["status"])
    if row["status"] != "ready_for_runtime":
        item["status"] = row["status"]
        summary.append(item)
        continue
    key = hashlib.sha256(row["config"].encode()).hexdigest()[:12]
    out = base / "runs" / key
    out.mkdir(parents=True, exist_ok=True)
    result = out / "result.json"
    if not result.exists() or json.loads(result.read_text()).get("status") == "initializing":
        with (base / "gpu.lock").open("a") as lock, (out / "stdout.log").open("w") as log:
            fcntl.flock(lock, fcntl.LOCK_EX)
            proc = subprocess.Popen(
                [
                    "bash",
                    str(r / "run_env41.sh"),
                    str(base / "run_one.py"),
                    str(repo / "workflows/simbox/core/configs/tasks" / row["config"]),
                    str(out),
                ],
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                cwd=w,
            )
            try:
                proc.wait(timeout=a.timeout)
            except subprocess.TimeoutExpired:
                terminate_group(proc)
                prior = json.loads(result.read_text()) if result.exists() else {}
                prior["planning_status_before_timeout"] = prior.get("status")
                prior.update(
                    status="shutdown_timeout"
                    if prior.get("status") == "planning_succeeded"
                    else "timeout",
                    timeout_seconds=a.timeout,
                )
                result.write_text(json.dumps(prior, indent=2))
    item.update(
        json.loads(result.read_text()) if result.exists() else dict(status="process_failed")
    )
    item["config"] = row["config"]
    item["run_dir"] = str(out.relative_to(base))
    summary.append(item)
    (base / "runtime-results.json").write_text(json.dumps(summary, indent=2))
    print("FINISHED", row["config"], item["status"], flush=True)
(base / "runtime-results.json").write_text(json.dumps(summary, indent=2))
from collections import Counter

print("AUDIT_DONE", dict(Counter(x["status"] for x in summary)), flush=True)
