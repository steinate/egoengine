"""Fetch only selected task assets, reuse validated files, never fetch episode archives."""

import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import time
import urllib.request
import urllib.parse

PREFIXES = [
    "basic/hang_the_cup_on_rack/cup/cup2",
    "basic/hang_the_cup_on_rack/cup_shelf/cup_shelf0",
    "art/microwave_gr/microwave7119",
    "basic/insert_the_flower_in_vase/flower1",
    "basic/insert_the_flower_in_vase/vase",
]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("root", type=Path)
    p.add_argument("--endpoint", default="https://huggingface.co")
    p.add_argument("--token-file", type=Path)
    p.add_argument("--download", action="store_true")
    p.add_argument("--prefix", action="append")
    a = p.parse_args()
    token = a.token_file.read_text().strip() if a.token_file else ""
    repo = "InternRobotics/InternData-A1"
    records = []
    for prefix in a.prefix or PREFIXES:
        url = f"{a.endpoint}/api/datasets/{repo}/tree/main/InternDataAssets/assets/{prefix}?recursive=true&limit=1000"
        request = urllib.request.Request(url)
        if token:
            request.add_unredirected_header("Authorization", "Bearer " + token)
        with urllib.request.urlopen(request, timeout=40) as r:
            records += [
                x
                for x in json.load(r)
                if x["type"] == "file"
                and not x["path"].lower().endswith((".obj", ".mtl"))
                and "copy" not in Path(x["path"]).name.lower()
            ]
            assert not r.headers.get("Link"), "Paginated asset listing needs another page"
    assert all(not x.get("lfs") or "*" not in x["lfs"]["oid"] for x in records), (
        "Dataset metadata needs authorized access to reveal hashes"
    )
    folder = a.root / "task-pairs"
    folder.mkdir(exist_ok=True)
    manifest = folder / "asset-manifest.json"
    existing = json.loads(manifest.read_text()) if manifest.exists() else []
    combined = {x["path"]: x for x in existing + records}
    manifest.write_text(json.dumps(list(combined.values()), indent=2))
    print("ASSET_SUBSET", len(records), sum(x["size"] for x in records), flush=True)

    def matches(path, entry):
        if not path.is_file() or path.stat().st_size != entry["size"]:
            return False
        data = path.read_bytes()
        if entry.get("lfs"):
            return hashlib.sha256(data).hexdigest() == entry["lfs"]["oid"]
        return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest() == entry["oid"]

    def fetch(entry):
        path = a.root / "assets" / entry["path"]
        if matches(path, entry):
            return
        if not a.download:
            print("MISSING", entry["path"], entry["size"], flush=True)
            return
        if path.exists():
            raise RuntimeError(f"Existing asset differs: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + ".download-part")
        if matches(temp, entry):
            temp.rename(path)
            print("RECOVERED_VERIFIED", entry["path"], flush=True)
            return
        for attempt in range(5):
            request = urllib.request.Request(
                f"{a.endpoint}/datasets/{repo}/resolve/main/{urllib.parse.quote(entry['path'], safe='/')}"
            )
            if token:
                request.add_unredirected_header("Authorization", "Bearer " + token)
            try:
                with urllib.request.urlopen(request, timeout=60) as r, temp.open("wb") as w:
                    while chunk := r.read(1024 * 1024):
                        w.write(chunk)
                assert matches(temp, entry), entry["path"]
                temp.rename(path)
                print("VERIFIED", entry["path"], flush=True)
                return
            except Exception as error:
                print("RETRY", entry["path"], type(error).__name__, flush=True)
                if attempt == 4:
                    raise
                time.sleep(2**attempt)

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(fetch, records))
    print("ASSET_AUDIT_DONE", flush=True)


if __name__ == "__main__":
    main()
