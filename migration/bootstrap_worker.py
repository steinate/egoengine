"""Fetch only the original Worker and license files from NVIDIA's sample ZIP.

Uses HTTP ranges, ZIP CRC validation and a local SHA256 inventory. The recorded
SHA256 is provenance, not an independently published vendor checksum.
"""

from concurrent.futures import ThreadPoolExecutor
import threading
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import urllib.request
import zipfile
import zlib
import time

URL = "https://d4i3qtqj3r0z5.cloudfront.net/Characters_NVD%4010012.zip"


class RemoteZip(io.RawIOBase):
    def __init__(self):
        for attempt in range(4):
            try:
                with urllib.request.urlopen(
                    urllib.request.Request(URL, method="HEAD"), timeout=30
                ) as r:
                    self.size = int(r.headers["Content-Length"])
                    self.etag = r.headers["ETag"]
                break
            except (OSError, urllib.error.URLError):
                if attempt == 3:
                    raise
                time.sleep(2**attempt)
        self.pos = 0
        self.transferred = 0

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        self.pos = offset + (0 if whence == 0 else self.pos if whence == 1 else self.size)
        return self.pos

    def read(self, size=-1):
        end = self.size if size < 0 else min(self.pos + size, self.size)
        if end <= self.pos:
            return b""
        req = urllib.request.Request(
            URL, headers={"Range": f"bytes={self.pos}-{end - 1}", "If-Match": self.etag}
        )
        for attempt in range(6):
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    expected = f"bytes {self.pos}-{end - 1}/{self.size}"
                    if r.status != 206 or r.headers.get("Content-Range") != expected:
                        raise RuntimeError("Publisher did not honor range/asset identity")
                    data = r.read()
                if len(data) != end - self.pos:
                    raise IOError("Incomplete range")
                break
            except (OSError, urllib.error.URLError) as exc:
                if attempt == 5:
                    raise
                print("RANGE_RETRY", self.pos, type(exc).__name__, flush=True)
                time.sleep(2**attempt)
        self.pos = end
        self.transferred += len(data)
        return data


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("root", type=Path)
    p.add_argument("--list", action="store_true")
    a = p.parse_args()
    root = a.root.resolve() / "human41/assets/characters"
    remote = RemoteZip()
    pinned = json.loads(
        (Path(__file__).resolve().parents[1] / "provenance/worker-assets.json").read_text()
    )
    if remote.etag != pinned["etag"] or remote.size != pinned["archive_bytes"]:
        raise RuntimeError("Publisher archive changed; review the pinned Worker inventory")
    expected_files = {f["path"]: f for f in pinned["files"]}
    entries = []
    with zipfile.ZipFile(remote) as archive:
        selected = [
            i
            for i in archive.infolist()
            if not i.is_dir()
            and (
                "/Reallusion/Worker/" in i.filename
                or any(s in i.filename.lower() for s in ["readme", "license", "eula"])
            )
        ]
        if a.list:
            print(
                json.dumps(
                    {
                        "files": [i.filename for i in selected],
                        "compressed_bytes": sum(i.compress_size for i in selected),
                    },
                    indent=2,
                )
            )
            return
        state = threading.local()
        readers = [remote]

        def fetch(info):
            rel = PurePosixPath(info.filename)
            if rel.is_absolute() or ".." in rel.parts:
                raise ValueError(f"Unsafe ZIP path: {rel}")
            target = root / rel
            expected_file = expected_files[str(rel)]
            if (info.file_size, info.CRC) != (expected_file["bytes"], expected_file["zip_crc32"]):
                raise RuntimeError(f"ZIP metadata differs from recorded inventory: {rel}")
            existing = target.read_bytes() if target.is_file() else None
            valid = (
                existing is not None
                and len(existing) == info.file_size
                and zlib.crc32(existing) == info.CRC
            )
            if existing is not None and not valid:
                raise RuntimeError(f"Existing asset differs; refusing overwrite: {target}")
            if not valid and not hasattr(state, "archive"):
                reader = RemoteZip.__new__(RemoteZip)
                reader.size, reader.etag = remote.size, remote.etag
                reader.pos, reader.transferred = 0, 0
                readers.append(reader)
                state.archive = zipfile.ZipFile(reader)
            data = existing if valid else state.archive.read(info)
            if hashlib.sha256(data).hexdigest() != expected_file["sha256"]:
                raise RuntimeError(f"SHA256 mismatch against recorded inventory: {rel}")
            if not valid:
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.with_name(target.name + ".part")
                temporary.write_bytes(data)
                temporary.replace(target)
            result = {
                "path": str(rel),
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "zip_crc32": info.CRC,
            }
            print("REUSED" if valid else "DOWNLOADED", str(rel), len(data), flush=True)
            return result

        with ThreadPoolExecutor(max_workers=6) as pool:
            entries = list(pool.map(fetch, selected))
    expected = root / "Assets/Characters/Reallusion/Worker/Props/Worker.usd"
    if not expected.is_file():
        raise RuntimeError("Worker USD missing from publisher archive")
    (root / "download-provenance.json").write_text(
        json.dumps(
            {
                "url": URL,
                "etag": remote.etag,
                "archive_bytes": remote.size,
                "transferred_bytes_this_run": sum(r.transferred for r in readers),
                "files": entries,
                "usage": "Original evaluation sample; bundled vendor license applies.",
            },
            indent=2,
        )
        + "\n"
    )
    print("WORKER_ASSET_READY", expected, flush=True)


if __name__ == "__main__":
    main()
