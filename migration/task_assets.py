"""List the recorded stack/lift asset subset; network access requires --download."""

import argparse
import hashlib
import json
from pathlib import Path
import urllib.request


MANIFEST = Path(__file__).resolve().parents[1] / "provenance/interndata-asset-downloads.json"
PREFIXES = tuple(
    "InternDataAssets/" + p
    for p in [
        "assets/split_aloha_mid_360/",
        "assets/basic/stack_lift/",
        "assets/table0/",
        "assets/envmap_lib/",
        "assets/background_textures/",
        "assets/floor_textures/",
        "assets/table_textures/",
        "curobo/src/curobo/content/",
        "panda_drake/",
    ]
)


def selected_files():
    return [
        f
        for f in json.loads(MANIFEST.read_text())["files"]
        if f["path"].startswith(PREFIXES)
        or f["path"] == "InternDataAssets/assets/table_info.json"
        or "official-distractor-manifest.json" in f["groups"]
    ]


def matches(path, entry):
    if not path.is_file() or path.stat().st_size != entry["bytes"]:
        return False
    sha256 = entry["upstream_lfs_sha256"]
    digest = hashlib.sha256() if sha256 else hashlib.sha1()
    if not sha256:
        digest.update(f"blob {entry['bytes']}\0".encode())
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest() == (sha256 or entry["git_blob_oid"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, help="Deployment root, required for verify/download")
    parser.add_argument("--output", type=Path, help="Write selected URLs, sizes and hashes as JSON")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--download", action="store_true", help="Explicitly fetch missing files")
    mode.add_argument("--verify", action="store_true", help="Read-only local hash verification")
    args = parser.parse_args()
    files = selected_files()
    print(
        json.dumps(
            {
                "files": len(files),
                "bytes": sum(f["bytes"] for f in files),
                "network_enabled": args.download,
            }
        )
    )
    if args.output:
        args.output.write_text(json.dumps({"files": files}, indent=2) + "\n")
    if not (args.download or args.verify):
        return
    if args.root is None:
        parser.error("--root is required")
    failures = []
    for entry in files:
        dest = args.root / "assets" / entry["path"]
        if matches(dest, entry):
            continue
        if args.verify:
            failures.append(entry["path"])
            continue
        if dest.exists() or dest.is_symlink():
            raise RuntimeError(f"Existing asset differs; refusing to overwrite: {dest}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        temp = dest.with_name(dest.name + ".ego-download-part")
        # An exclusive temporary file prevents overwriting a previous interrupted transfer.
        with (
            urllib.request.urlopen(entry["url"], timeout=60) as response,
            temp.open("xb") as handle,
        ):
            while chunk := response.read(1024 * 1024):
                handle.write(chunk)
        if not matches(temp, entry):
            raise RuntimeError(f"Upstream content changed or transfer corrupt: {temp}")
        temp.rename(dest)
        print("VERIFIED", entry["path"], flush=True)
    if failures:
        print(json.dumps({"missing_or_changed": failures}, indent=2))
        raise SystemExit(1)
    print("ALL_SELECTED_ASSETS_VERIFIED")


if __name__ == "__main__":
    main()
