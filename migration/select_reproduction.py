"""Stage a complete runnable deployment, omitting only redundant generated outputs.

The unfiltered archival snapshot remains separate. Every omitted path is recorded.
No stage input, model, texture, trajectory, planning output, environment, or runtime
is excluded. Current Amber skin caches and preview warm caches are retained.
"""

import argparse
import json
import os
from pathlib import Path
import shutil


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    source = args.source.resolve()
    destination = args.destination.resolve()
    if destination.exists():
        parser.error("Destination must not exist")
    destination.mkdir(parents=True)
    omitted = []

    def reason(parts, is_dir):
        # Runtime, assets, and Python/CUDA environments are copied in full.
        if parts[0] in {"runtime41", "env", "assets"}:
            return None
        if parts[0] in {"cache", "downloads", "logs", "logs41", "tmp", "backups41"}:
            return "redundant downloads, logs, or disposable runtime cache"
        if parts[0] == "cache41":
            if len(parts) > 1 and parts[1] not in {"kit-anime-both-preview", "torch", "warp"}:
                return "disposable cache; Amber warm cache and JIT caches retained"
            return None
        if len(parts) == 2 and is_dir and parts[1] in {"render", "preview", "delivery"}:
            return "encoded delivery or generated image frames; source data retained"
        if len(parts) == 2 and is_dir and parts[1] in {"skin-cache", "scan-cache"}:
            if parts[0] != "anime-human-v1":
                return "regenerable earlier-stage skin cache; Amber cache retained"
        if "__pycache__" in parts:
            return "regenerable Python bytecode"
        if len(parts) <= 2 and parts[-1].endswith((".tgz", ".zip", ".tar.gz", ".log")):
            return "redundant archive or log; expanded source tree retained"
        return None

    def copy(path):
        rel = path.relative_to(source)
        why = reason(rel.parts, path.is_dir() and not path.is_symlink())
        if why:
            omitted.append({"path": str(rel), "reason": why})
            return
        out = destination / rel
        if path.is_symlink():
            out.symlink_to(os.readlink(path))
        elif path.is_dir():
            out.mkdir()
            for child in sorted(path.iterdir()):
                copy(child)
        elif path.is_file():
            try:
                os.link(path, out)
            except OSError:
                shutil.copy2(path, out)
        else:
            raise RuntimeError(f"Unexpected special file: {path}")

    for path in sorted(source.iterdir()):
        copy(path)
    (destination / "MIGRATION-SELECTION.json").write_text(
        json.dumps({"original_root": str(source), "omitted": omitted}, indent=2) + "\n"
    )
    print("STAGED", destination, "omitted entries", len(omitted), flush=True)


if __name__ == "__main__":
    main()
