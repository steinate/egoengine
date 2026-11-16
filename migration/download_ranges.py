"""Resume a large public HTTPS file using verified HTTP byte ranges."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import time
import urllib.request


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("url")
    p.add_argument("output", type=Path)
    p.add_argument("--size", type=int, required=True)
    p.add_argument("--workers", type=int, default=8)
    a = p.parse_args()
    chunk = 64 * 1024 * 1024
    parts = a.output.with_name(a.output.name + ".parts")
    parts.mkdir(parents=True, exist_ok=True)
    metadata = parts / "source.json"
    source = {"url": a.url, "size": a.size, "chunk": chunk}
    if metadata.exists():
        assert json.loads(metadata.read_text()) == source, "Resume source changed"
    else:
        metadata.write_text(json.dumps(source, indent=2))
    partial = a.output.with_name(a.output.name + ".part")
    # Preserve the prefix fetched by a previous single-stream curl invocation.
    if partial.exists() and not (parts / "prefix-imported").exists():
        with partial.open("rb") as f:
            for index in range((a.size + chunk - 1) // chunk):
                data = f.read(chunk)
                if not data:
                    break
                path = parts / f"{index:05d}"
                if not path.exists():
                    path.write_bytes(data)
        (parts / "prefix-imported").touch()

    def fetch(index):
        start = index * chunk
        end = min(start + chunk, a.size) - 1
        target = parts / f"{index:05d}"
        for attempt in range(6):
            n = target.stat().st_size if target.exists() else 0
            assert n <= end - start + 1
            if n == end - start + 1:
                return index
            offset = start + n
            request = urllib.request.Request(
                a.url, headers={"Range": f"bytes={offset}-{end}", "Accept-Encoding": "identity"}
            )
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    assert response.status == 206, response.status
                    assert response.headers["Content-Range"] == f"bytes {offset}-{end}/{a.size}"
                    with target.open("ab") as out:
                        remaining = end - offset + 1
                        while remaining:
                            data = response.read(min(1024 * 1024, remaining))
                            if not data:
                                raise IOError("Truncated HTTP range")
                            out.write(data)
                            remaining -= len(data)
                return index
            except Exception as error:
                print(f"RANGE_RETRY {index} attempt={attempt + 1}: {error}", flush=True)
                if attempt == 5:
                    raise
                time.sleep(min(2**attempt, 15))

    count = (a.size + chunk - 1) // chunk
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        for finished, future in enumerate(
            as_completed([pool.submit(fetch, i) for i in range(count)]), 1
        ):
            index = future.result()
            print(f"RANGE_READY {index} completed={finished}/{count}", flush=True)
    digest = hashlib.sha256()
    with partial.open("wb") as output:
        for i in range(count):
            with (parts / f"{i:05d}").open("rb") as handle:
                while data := handle.read(1024 * 1024):
                    digest.update(data)
                    output.write(data)
    assert partial.stat().st_size == a.size
    partial.replace(a.output)
    a.output.with_name(a.output.name + ".sha256").write_text(
        f"{digest.hexdigest()}  {a.output.name}\n"
    )
    print("DOWNLOAD_COMPLETE", a.output, digest.hexdigest(), flush=True)


if __name__ == "__main__":
    main()
