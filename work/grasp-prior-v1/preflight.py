"""Inventory pinned sources/models without downloading datasets or loading pickle files."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def inspect(root, spec, overrides):
    report = {"root": str(root), "repositories": {}, "models": {}}
    for name, source in spec["repositories"].items():
        folder = root / "sources" / name
        entry = {**source, "path": str(folder), "ready": False}
        if (folder / ".git").exists():
            rev = subprocess.check_output(
                ["git", "-C", str(folder), "rev-parse", "HEAD"], text=True
            ).strip()
            dirty = subprocess.check_output(
                ["git", "-C", str(folder), "status", "--porcelain"], text=True
            ).strip()
            entry.update(
                actual_commit=rev, dirty=bool(dirty), ready=rev == source["commit"] and not dirty
            )
        report["repositories"][name] = entry
    for name, model in spec["models"].items():
        path = Path(overrides.get(name, root / model["path"])).expanduser().resolve()
        entry = {
            "path": str(path),
            "official_url": model["official_url"],
            "note": model["note"],
            "present": path.is_file(),
        }
        if entry["present"]:
            size = path.stat().st_size
            with path.open("rb") as f:
                prefix = f.read(256)
            entry.update(bytes=size, sha256=digest(path))
            entry["present"] = size > 0 and not prefix.startswith(
                b"version https://git-lfs.github.com/spec/"
            )
        report["models"][name] = entry
    report["files_ready"] = all(x["ready"] for x in report["repositories"].values()) and all(
        x["present"] for x in report["models"].values()
    )
    report["note"] = (
        "File inventory only. Does not assert authorization, model compatibility, successful inference, or quality."
    )
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("root", type=Path, help="Dedicated run/grasp-prior-v1 directory")
    p.add_argument(
        "--model-paths", type=Path, help="JSON mapping model keys to existing authorized file paths"
    )
    p.add_argument("--report", type=Path)
    a = p.parse_args()
    spec = json.loads(Path(__file__).with_name("sources.json").read_text())
    overrides = json.loads(a.model_paths.read_text()) if a.model_paths else {}
    unknown = set(overrides) - set(spec["models"])
    if unknown:
        p.error(f"Unknown model keys: {sorted(unknown)}")
    report = inspect(a.root.resolve(), spec, overrides)
    rendered = json.dumps(report, indent=2)
    if a.report:
        a.report.parent.mkdir(parents=True, exist_ok=True)
        a.report.write_text(rendered + "\n")
    print(rendered)
    raise SystemExit(0 if report["files_ready"] else 2)


if __name__ == "__main__":
    main()
