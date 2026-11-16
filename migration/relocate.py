"""Rebase a restored copy's project paths; never modify the original deployment."""

import argparse
import json
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--old-root", default="/vepfs/public/pengjiaqi/interndata-human-pair")
    parser.add_argument("--usd-only", action="store_true")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    old = args.old_root.rstrip("/")
    if root == Path(old).resolve():
        parser.error("Relocation requires a separate restored copy")
    changed = []
    text_suffixes = {
        ".py",
        ".sh",
        ".json",
        ".jsonl",
        ".yaml",
        ".yml",
        ".toml",
        ".cfg",
        ".ini",
        ".xml",
        ".mdl",
    }
    if args.usd_only:
        sys.path.insert(0, str(root / "runtime41/kit/exts/omni.usd.libs"))
        from pxr import Sdf, UsdUtils
    for directory, dirs, files in os.walk(root, followlinks=False):
        if args.usd_only and Path(directory) == root:
            # SDK/env/cache trees contain intentionally invalid parser test
            # fixtures. They are not project scenes and need no asset rebasing.
            dirs[:] = [name for name in dirs if name not in {"runtime41", "env", "cache41"}]
        for name in dirs + files:
            if name.startswith("._"):
                # AppleDouble metadata is not the USD file its suffix resembles.
                continue
            path = Path(directory) / name
            if path.is_symlink():
                target = os.readlink(path)
                if not args.usd_only and (target == old or target.startswith(old + "/")):
                    path.unlink()
                    path.symlink_to(str(root) + target[len(old) :])
                    changed.append(str(path.relative_to(root)))
                continue
            if not path.is_file():
                continue
            if args.usd_only:
                if path.suffix not in {".usd", ".usda", ".usdc"}:
                    continue
                layer = Sdf.Layer.FindOrOpen(str(path))
                if not layer:
                    raise RuntimeError(f"Cannot open USD layer: {path}")
                count = [0]

                def replace(asset):
                    new = asset.replace(old + "/", str(root) + "/")
                    count[0] += int(new != asset)
                    return new

                UsdUtils.ModifyAssetPaths(layer, replace)
                if count[0]:
                    layer.Save()
                    changed.append(str(path.relative_to(root)))
            elif path.suffix in text_suffixes:
                content = path.read_bytes()
                if old.encode() in content:
                    path.write_bytes(content.replace(old.encode(), str(root).encode()))
                    changed.append(str(path.relative_to(root)))
    args.report.write_text(
        json.dumps(
            {
                "old_root": old,
                "new_root": str(root),
                "usd_only": args.usd_only,
                "changed": changed,
                "note": "Rebased copy; original snapshot hashes remain immutable in the bundle.",
            },
            indent=2,
        )
        + "\n"
    )
    print("RELOCATED", len(changed), "paths", flush=True)


if __name__ == "__main__":
    main()
