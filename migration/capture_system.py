"""Capture non-secret userspace support files for the Ubuntu 24.04 deployment.

The host kernel and NVIDIA driver are platform prerequisites, not portable assets.
This supplement is kept private with the deployment, never added to public Git.
"""

import argparse
import json
from pathlib import Path
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    if args.destination.exists():
        parser.error("Destination already exists")
    args.destination.mkdir(parents=True)
    paths = [
        "/usr/lib/x86_64-linux-gnu",
        "/usr/lib/python3.12",
        "/usr/lib64",
        "/usr/share/blender",
        "/usr/share/fonts",
        "/usr/share/glvnd",
        "/usr/share/vulkan",
        "/usr/share/zoneinfo",
        "/etc/ssl/certs",
        "/etc/fonts",
        "/etc/os-release",
        "/etc/ld.so.cache",
        "/etc/nsswitch.conf",
    ]
    for command in [
        "bash",
        "env",
        "ffmpeg",
        "ffprobe",
        "blender",
        "python3.12",
        "tar",
        "gzip",
        "mkdir",
        "cp",
        "ln",
        "dirname",
        "readlink",
        "uname",
        "sed",
        "grep",
        "find",
    ]:
        executable = shutil.which(command)
        if executable:
            paths.append(str(Path(executable).resolve()))
    copied = []
    for name in sorted(set(paths)):
        source = Path(name)
        if not source.exists():
            continue
        target = args.destination / source.relative_to("/")
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target, symlinks=True, dirs_exist_ok=True)
        else:
            shutil.copy2(source, target, follow_symlinks=True)
        copied.append(name)
    for name in ("bin", "lib", "lib64", "sbin"):
        (args.destination / name).symlink_to("usr/" + name)
    packages = subprocess.check_output(
        ["dpkg-query", "-W", "-f=${Package}\t${Version}\n"], text=True
    )
    (args.destination / "packages.tsv").write_text(packages)
    (args.destination / "SYSTEM-SUPPORT.json").write_text(
        json.dumps(
            {
                "paths": copied,
                "scope": "Userspace support supplement, not a complete bootable OS or a kernel/driver installer",
            },
            indent=2,
        )
        + "\n"
    )
    print("SYSTEM_SUPPORT_CAPTURED", len(copied), flush=True)


if __name__ == "__main__":
    main()
