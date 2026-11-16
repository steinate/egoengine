"""Upload a private snapshot in parallel chunks and verify it on the destination."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shlex
import subprocess
import time

from build_snapshot import sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("host")
    parser.add_argument("remote")
    parser.add_argument("--port", default="22")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--prefix", default="local-work")
    args = parser.parse_args()
    ssh = ["ssh", "-o", "BatchMode=yes", "-p", args.port, args.host]
    remote = args.remote.rstrip("/")

    def remote_run(command, data=None):
        for attempt in range(5):
            result = subprocess.run([*ssh, command], input=data, capture_output=True)
            if result.returncode == 0:
                return result.stdout
            if result.returncode != 255:
                break
            time.sleep(attempt + 1)
        raise RuntimeError(f"SSH command failed: {command}: {result.stderr!r}")

    remote_run("mkdir -p " + shlex.quote(remote))
    index_name = args.prefix + "-index.json"
    index = json.loads((args.source / index_name).read_text())

    def put_small(name):
        remote_run("cat > " + shlex.quote(remote + "/" + name), (args.source / name).read_bytes())

    for item in index["archives"]:
        name = item["archive"]
        path = args.source / name
        assert sha256(path) == item["sha256"], name
        final = shlex.quote(remote + "/" + name)
        existing = remote_run(f"if test -f {final}; then sha256sum {final}; fi").decode().split()
        if existing and existing[0] == item["sha256"]:
            put_small(item["manifest"])
            put_small(name.replace(".tar.gz", ".summary.json"))
            print("VERIFIED_EXISTING_UPLOAD", name, flush=True)
            continue
        partial = remote + "/" + name + ".partial"
        remote_run("truncate -s " + str(path.stat().st_size) + " " + shlex.quote(partial))
        chunk_size = 16 * 1024 * 1024

        def upload(i):
            offset = i * chunk_size
            with path.open("rb") as stream:
                stream.seek(offset)
                data = stream.read(chunk_size)
            command = (
                "dd of="
                + shlex.quote(partial)
                + f" bs=1048576 oflag=seek_bytes seek={offset} conv=notrunc status=none"
            )
            for attempt in range(4):
                result = subprocess.run([*ssh, command], input=data, capture_output=True)
                if result.returncode == 0:
                    return
                time.sleep(attempt + 1)
            raise RuntimeError(f"Upload failed: {name} chunk {i}: {result.stderr!r}")

        chunks = range((path.stat().st_size + chunk_size - 1) // chunk_size)
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            list(pool.map(upload, chunks))
        digest = remote_run("sha256sum " + shlex.quote(partial)).decode().split()[0]
        assert digest == item["sha256"], name
        remote_run("mv " + shlex.quote(partial) + " " + shlex.quote(remote + "/" + name))
        put_small(item["manifest"])
        put_small(name.replace(".tar.gz", ".summary.json"))
        print("VERIFIED_UPLOAD", name, path.stat().st_size, flush=True)
    put_small(index_name)
    print("ALL_UPLOADS_VERIFIED", len(index["archives"]), flush=True)


if __name__ == "__main__":
    main()
