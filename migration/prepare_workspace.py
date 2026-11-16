"""Stage tracked workflow scripts in a new data directory; never download assets."""

import argparse
import json
from pathlib import Path
import shlex
import subprocess


OLD = "/vepfs/public/pengjiaqi/interndata-human-pair"
REPO = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    if root == Path(OLD) or root == REPO or REPO in root.parents:
        parser.error("Use a NEW deployment directory outside the checkout and original deployment")
    names = (
        subprocess.check_output(["git", "ls-files", "-z", "work"], cwd=REPO).decode().split("\0")
    )
    files = {}
    for name in names:
        path = Path(name)
        if len(path.parts) != 3 or path.parts[1] not in {
            "robot-stack-v2",
            "anime-human-v1",
            "human41",
            "human-natural-v4",
        }:
            continue
        content = (REPO / path).read_text()
        content = content.replace(OLD, str(root))
        if path.name == "configure.py":
            content = content.replace(
                'ENGINE = ROOT / "src/InternDataEngine41"', f"ENGINE = Path({str(REPO)!r})"
            )
        files[root / Path(*path.parts[1:])] = content
    files[root / "install_cuda118.py"] = (
        (REPO / "work/isaac41/install_cuda118.py").read_text().replace(OLD, str(root))
    )
    # Historical metadata is explicitly provenance, not a newly generated test result.
    for name in ["provenance.json", "camera-framing.json"]:
        files[root / "anime-human-v1" / name] = (REPO / "evidence/amber-upright" / name).read_text()
    files[root / "run_env41.sh"] = (
        "#!/usr/bin/env bash\nset -euo pipefail\nexec bash "
        + shlex.quote(str(REPO / "migration/run_engine.sh"))
        + " "
        + shlex.quote(str(root))
        + ' "$@"\n'
    )
    files[root / "human41/usd_python.sh"] = (
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        + "PAIR="
        + shlex.quote(str(root))
        + "\n"
        + 'export LD_LIBRARY_PATH="$PAIR/env/system/usr/lib/x86_64-linux-gnu:$PAIR/runtime41/kit/exts/omni.usd.libs/bin:$PAIR/runtime41/kit"\n'
        + 'export PATH="$PAIR/env/system/usr/bin:$PATH"\n'
        + 'export TMPDIR="$PAIR/tmp"\n'
        + 'export PYTHONPATH="$PAIR/env/python310:$PAIR/runtime41/kit/exts/omni.usd.libs"\n'
        + 'export PYTHONPYCACHEPREFIX="$PAIR/cache41/pycache"\n'
        + 'exec "$PAIR/runtime41/kit/python/bin/python3" "$@"\n'
    )
    links = {
        root / "src/InternDataEngine41": REPO,
        root / "anime-human-v1/source": root / "human-stack-v3/source",
        root / "human-natural-v4/source": root / "human-stack-v3/source",
        root / "anime-human-v1/reference/human-animation.npz": root
        / "human-natural-v4/human-animation.npz",
        root / "anime-human-v1/tools/blender_mmd_tools": REPO / "deps/blender_mmd_tools",
    }
    # Preflight every destination before writing any file.
    for path, content in files.items():
        if path.is_symlink() or (
            path.exists() and (not path.is_file() or path.read_text() != content)
        ):
            parser.error(f"Refusing to replace existing different file: {path}")
    for path, target in links.items():
        if (path.exists() or path.is_symlink()) and (
            not path.is_symlink() or path.resolve() != target.resolve()
        ):
            parser.error(f"Refusing to replace existing different path: {path}")
    for name in [
        "env/python310",
        "env/curobo41-built",
        "tmp",
        "logs41",
        "logs",
        "cache41",
        "downloads",
        "human-stack-v3/source",
        "human-natural-v4",
        "human41/output",
    ]:
        (root / name).mkdir(parents=True, exist_ok=True)
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    for path, target in links.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.is_symlink():
            path.symlink_to(target)
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    (root / "workspace-source.json").write_text(
        json.dumps(
            {
                "checkout": str(REPO),
                "revision": revision,
                "files": [str(p.relative_to(root)) for p in files],
            },
            indent=2,
        )
        + "\n"
    )
    print(f"Prepared {len(files)} text files in {root}; no assets downloaded")


if __name__ == "__main__":
    main()
