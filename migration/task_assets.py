"""List the recorded stack/lift asset subset; network access requires --download."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import time
from pathlib import Path
import urllib.request
import urllib.error


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
    parser.add_argument("--token-file", type=Path, help="Hugging Face read token; never printed")
    parser.add_argument(
        "--endpoint",
        choices=["https://huggingface.co", "https://hf-mirror.com"],
        default="https://huggingface.co",
        help="Mirror receives the token only when explicitly selected",
    )
    parser.add_argument("--workers", type=int, default=4)
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
    token = (
        args.token_file.read_text().strip() if args.token_file else os.environ.get("HF_TOKEN", "")
    )

    def process(entry):
        dest = args.root / "assets" / entry["path"]
        if matches(dest, entry):
            return None
        if args.verify:
            return entry["path"]
        if dest.exists() or dest.is_symlink():
            raise RuntimeError(f"Existing asset differs; refusing to overwrite: {dest}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        temp = dest.with_name(dest.name + ".ego-download-part")
        url = entry["url"].replace("https://huggingface.co", args.endpoint, 1)
        for attempt in range(5):
            request = urllib.request.Request(url)
            if token:
                # Do not forward credentials to signed object-storage redirects.
                request.add_unredirected_header("Authorization", "Bearer " + token)
            offset = temp.stat().st_size if temp.exists() else 0
            if offset and matches(temp, entry):
                break
            if offset:
                request.add_header("Range", f"bytes={offset}-")
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    mode = "ab" if offset and response.status == 206 else "wb"
                    if mode == "ab":
                        assert response.headers.get("Content-Range", "").startswith(
                            f"bytes {offset}-"
                        )
                    with temp.open(mode) as handle:
                        while chunk := response.read(1024 * 1024):
                            handle.write(chunk)
                break
            except urllib.error.HTTPError as error:
                if error.code in {401, 403, 404} or attempt == 4:
                    raise
                time.sleep(min(2**attempt, 15))
            except (OSError, urllib.error.URLError):
                if attempt == 4:
                    raise
                time.sleep(min(2**attempt, 15))
        if not matches(temp, entry):
            raise RuntimeError(f"Upstream content changed or transfer corrupt: {temp}")
        temp.rename(dest)
        print("VERIFIED", entry["path"], flush=True)
        return None

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        failures = [result for result in pool.map(process, files) if result]
    if failures:
        print(json.dumps({"missing_or_changed": failures}, indent=2))
        raise SystemExit(1)
    print("ALL_SELECTED_ASSETS_VERIFIED")


if __name__ == "__main__":
    main()
