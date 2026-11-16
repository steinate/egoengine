"""Check tracked Python syntax and shell syntax without importing Isaac Sim."""

import ast
import subprocess
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    paths = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode().split("\0")
    python_count = shell_count = 0
    for name in filter(None, paths):
        if not (
            name.startswith(("work/", "migration/", "human_pair/"))
            or name in ("scripts/check_sources.py", "scripts/format_sources.py")
        ):
            continue
        path = root / name
        if path.suffix == ".py":
            ast.parse(path.read_text(encoding="utf-8"), filename=name)
            python_count += 1
        elif path.suffix == ".sh":
            subprocess.run(["bash", "-n", str(path)], check=True)
            shell_count += 1
    print(f"Syntax OK: {python_count} Python files, {shell_count} shell files")


if __name__ == "__main__":
    main()
