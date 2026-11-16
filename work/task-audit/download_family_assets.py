"""Download the reviewed family asset manifest, reuse matching files, and verify every hash."""

import argparse, concurrent.futures, hashlib, json, threading, time, urllib.request, urllib.parse
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("workspace", type=Path)
p.add_argument("--download", action="store_true")
p.add_argument("--workers", type=int, default=4)
a = p.parse_args()
w = a.workspace
b = w / "run/task-audit"
root = w / "run/assets"
manifest = json.loads((b / "family-assets.json").read_text())
files = manifest["files"]
token = (w / "config/hf_token").read_text().strip()
assert all(not x.get("lfs") or "*" not in x["lfs"]["oid"] for x in files)
print("MANIFEST", len(files), manifest["additional_bytes"], "download", a.download, flush=True)
lock = threading.Lock()
results = []


def digest(path, entry):
    if not path.is_file() or path.stat().st_size != entry["size"]:
        return False
    h = hashlib.sha256() if entry.get("lfs") else hashlib.sha1()
    if not entry.get("lfs"):
        h.update(f"blob {entry['size']}\0".encode())
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest() == entry.get("lfs", {}).get("oid", entry["oid"])


def fetch(entry):
    path = root / entry["path"]
    result = dict(path=entry["path"], bytes=entry["size"])
    try:
        if digest(path, entry):
            result["status"] = "reused"
        elif path.exists():
            raise RuntimeError("Existing file differs; not overwritten")
        elif not a.download:
            result["status"] = "missing"
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            part = path.with_name(path.name + ".audit-part")
            for attempt in range(5):
                if digest(part, entry):
                    break
                req = urllib.request.Request(
                    "https://hf-mirror.com/datasets/InternRobotics/InternData-A1/resolve/main/"
                    + urllib.parse.quote(entry["path"], safe="/")
                )
                req.add_unredirected_header("Authorization", "Bearer " + token)
                offset = part.stat().st_size if part.exists() else 0
                if offset >= entry["size"]:
                    part.unlink()
                    offset = 0
                if offset:
                    req.add_header("Range", f"bytes={offset}-")
                try:
                    with urllib.request.urlopen(req, timeout=60) as response:
                        mode = "ab" if offset and response.status == 206 else "wb"
                        if mode == "ab":
                            assert response.headers["Content-Range"].startswith(f"bytes {offset}-")
                        with part.open(mode) as dest:
                            while block := response.read(1024 * 1024):
                                dest.write(block)
                    assert digest(part, entry), "Downloaded hash mismatch"
                    break
                except Exception:
                    if attempt == 4:
                        raise
                    time.sleep(2**attempt)
            assert digest(part, entry)
            part.replace(path)
            result["status"] = "downloaded"
    except Exception as error:
        result.update(status="failed", error=str(error))
    with lock:
        results.append(result)
        if len(results) % 25 == 0 or result["status"] == "failed":
            print("PROGRESS", len(results), len(files), result["status"], entry["path"], flush=True)
    return result


with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
    list(pool.map(fetch, files))
(b / "family-asset-download-results.json").write_text(json.dumps(results, indent=2))
from collections import Counter

print("DOWNLOAD_DONE", dict(Counter(x["status"] for x in results)), flush=True)
if any(x["status"] == "failed" for x in results):
    raise SystemExit(1)
