"""Format only Python files tracked by this repository, never nested dependencies."""

import argparse
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ruff", default="ruff")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    names = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode().split("\0")
    # Preserve the upstream engine's formatting; only format our workflow tools.
    paths = [
        name
        for name in names
        if name.endswith(".py")
        and (
            name.startswith(("work/", "migration/"))
            or name in ("scripts/check_sources.py", "scripts/format_sources.py")
        )
    ]
    if paths:
        command = [args.ruff, "format"]
        if args.check:
            command.append("--check")
        subprocess.run([*command, *paths], cwd=root, check=True)


if __name__ == "__main__":
    main()
