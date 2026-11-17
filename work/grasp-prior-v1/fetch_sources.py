"""Fetch pinned upstream code directly on the target machine; reuse matching checkouts."""

import argparse
import json
from pathlib import Path
import subprocess


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("root", type=Path)
    p.add_argument("--only", nargs="+")
    a = p.parse_args()
    repositories = json.loads(Path(__file__).with_name("sources.json").read_text())["repositories"]
    if a.only and set(a.only) - set(repositories):
        p.error("Unknown repository")
    root = a.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    for name, spec in repositories.items():
        if a.only and name not in a.only:
            continue
        target = root / "sources" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if not (target / ".git").is_dir():
                raise RuntimeError(f"Refusing to replace existing non-Git directory: {target}")
            head = subprocess.check_output(
                ["git", "-C", str(target), "rev-parse", "HEAD"], text=True
            ).strip()
            dirty = subprocess.check_output(
                ["git", "-C", str(target), "status", "--porcelain"], text=True
            ).strip()
            if head != spec["commit"] or dirty:
                raise RuntimeError(f"Existing checkout differs; preserve it and review: {target}")
            print("REUSE", name, head, flush=True)
            continue
        subprocess.run(
            ["git", "clone", "--filter=blob:none", "--no-checkout", spec["url"], str(target)],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(target), "checkout", "--detach", spec["commit"]], check=True
        )
        head = subprocess.check_output(
            ["git", "-C", str(target), "rev-parse", "HEAD"], text=True
        ).strip()
        if head != spec["commit"]:
            raise RuntimeError(f"Revision mismatch: {name}")
        print("FETCHED", name, head, flush=True)


if __name__ == "__main__":
    main()
