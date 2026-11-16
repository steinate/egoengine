"""Exercise one original configuration per source family, reusing completed audit attempts."""

import argparse
import collections
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time

p = argparse.ArgumentParser()
p.add_argument("workspace", type=Path)
p.add_argument("--timeout", type=int, default=600)
p.add_argument("--wait-for-assets", type=int, default=0)
p.add_argument("--family", action="append", help="Only these exact source families")
p.add_argument("--tag", help="Save a separate retest without replacing baseline results")
a = p.parse_args()
if a.tag and (not a.tag.replace("-", "").replace("_", "").isalnum()):
    p.error("tag may contain letters, digits, hyphens and underscores")
w = a.workspace
base = w / "run/task-audit"
repo = w / "egoengine"
batch_lock = (base / "family-batch.lock").open("a")
fcntl.flock(batch_lock, fcntl.LOCK_EX)
manifest = json.loads((base / "family-assets.json").read_text())
rows = manifest["selected"]
if a.family:
    assert set(a.family) <= {row["family"] for row in rows}, "Unknown family"
    rows = [row for row in rows if row["family"] in a.family]
result_root = base / "retests" / a.tag if a.tag else base
result_root.mkdir(parents=True, exist_ok=True)
summary = []
for row in rows:
    item = {k: row[k] for k in ["family", "config", "embodiment", "unresolved"]}
    deadline = time.monotonic() + a.wait_for_assets
    while True:
        pending = [name for name in row["files"] if not (w / "run/assets" / name).is_file()]
        if not pending or time.monotonic() >= deadline:
            break
        time.sleep(5)
    if pending:
        item["unresolved"] = ["asset download not complete: " + name for name in pending]
    if item["unresolved"]:
        item["status"] = "blocked_dependencies"
    else:
        key = hashlib.sha256(row["config"].encode()).hexdigest()[:12]
        out = result_root / "runs" / key
        out.mkdir(parents=True, exist_ok=True)
        result = out / "result.json"
        with (base / "gpu.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            previous = json.loads(result.read_text()) if result.exists() else {}
            item["reused_attempt"] = bool(previous and previous.get("status") != "initializing")
            if not item["reused_attempt"]:
                with (out / "stdout.log").open("w") as log:
                    proc = subprocess.Popen(
                        [
                            "bash",
                            str(w / "run/run_env41.sh"),
                            str(base / "run_one.py"),
                            str(repo / "workflows/simbox/core/configs/tasks" / row["config"]),
                            str(out),
                        ],
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        cwd=w,
                        start_new_session=True,
                    )
                    try:
                        proc.wait(timeout=a.timeout)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid, signal.SIGTERM)
                        try:
                            proc.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            os.killpg(proc.pid, signal.SIGKILL)
                            proc.wait()
                        prior = json.loads(result.read_text()) if result.exists() else {}
                        # A shutdown hang must not erase a completed planning outcome.
                        prior["planning_status_before_timeout"] = prior.get("status")
                        prior.update(
                            status="shutdown_timeout"
                            if prior.get("status") == "planning_succeeded"
                            else "timeout",
                            timeout_seconds=a.timeout,
                        )
                        result.write_text(json.dumps(prior, indent=2))
            item.update(
                json.loads(result.read_text()) if result.exists() else {"status": "process_failed"}
            )
        item["config"] = row["config"]
        item["run_dir"] = str(out.relative_to(base))
    summary.append(item)
    (result_root / "family-runtime-results.json").write_text(json.dumps(summary, indent=2))
    print("FAMILY_FINISHED", len(summary), len(rows), row["family"], item["status"], flush=True)
print("FAMILIES_DONE", dict(collections.Counter(x["status"] for x in summary)), flush=True)
