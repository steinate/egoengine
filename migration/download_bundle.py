"""Resume private snapshot downloads over SSH and verify complete archive hashes."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import time

from build_snapshot import sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host")
    parser.add_argument("remote")
    parser.add_argument("destination", type=Path)
    parser.add_argument("--port", default="22")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--prefix", default="deployment")
    args = parser.parse_args()
    args.destination.mkdir(parents=True, exist_ok=True)
    ssh = ["ssh", "-o", "BatchMode=yes", "-o", "Compression=no", "-p", args.port, args.host]
    remote = args.remote.rstrip("/")

    def fetch_bytes(name):
        return subprocess.check_output([*ssh, "cat " + shlex.quote(remote + "/" + name)])

    verified = set()
    while True:
        query = (
            "import pathlib,json; p=pathlib.Path(" + repr(remote) + "); "
            "print(json.dumps({'summaries':[json.loads(f.read_text()) for f in "
            "p.glob(" + repr(args.prefix + "-*.summary.json") + ")], "
            "'complete':(p/" + repr(args.prefix + "-index.json") + ").exists()}))"
        )
        state = json.loads(subprocess.check_output([*ssh, "python3 -c " + shlex.quote(query)]))
        for summary in state["summaries"]:
            name = summary["archive"]
            if name in verified:
                continue
            output = args.destination / name
            if output.exists():
                if sha256(output) != summary["sha256"]:
                    raise RuntimeError(f"Existing download hash mismatch: {output}")
            else:
                partial = Path(str(output) + ".partial")
                markers = Path(str(output) + ".chunks")
                markers.mkdir(exist_ok=True)
                fd = os.open(partial, os.O_CREAT | os.O_RDWR, 0o600)
                os.ftruncate(fd, summary["archive_bytes"])
                chunk_size = 16 * 1024 * 1024
                chunks = range((summary["archive_bytes"] + chunk_size - 1) // chunk_size)

                def download_chunk(i):
                    start = i * chunk_size
                    length = min(chunk_size, summary["archive_bytes"] - start)
                    marker = markers / str(i)
                    if marker.exists():
                        return length
                    command = (
                        "dd if="
                        + shlex.quote(remote + "/" + name)
                        + f" bs=1048576 iflag=skip_bytes,count_bytes skip={start} count={length} status=none"
                    )
                    for attempt in range(4):
                        data = subprocess.run(
                            [*ssh, command], stdout=subprocess.PIPE, stderr=subprocess.PIPE
                        )
                        if data.returncode == 0 and len(data.stdout) == length:
                            written = 0
                            while written < length:
                                written += os.pwrite(fd, data.stdout[written:], start + written)
                            marker.write_text(hashlib.sha256(data.stdout).hexdigest())
                            return length
                        time.sleep(attempt + 1)
                    raise RuntimeError(
                        f"Chunk failed: {name} {i}: {data.stderr.decode(errors='replace')}"
                    )

                done = 0
                last = time.time()
                try:
                    with ThreadPoolExecutor(max_workers=args.workers) as pool:
                        for future in as_completed(
                            [pool.submit(download_chunk, i) for i in chunks]
                        ):
                            done += future.result()
                            if time.time() - last > 30:
                                print(name, done, "/", summary["archive_bytes"], flush=True)
                                last = time.time()
                    os.fsync(fd)
                finally:
                    os.close(fd)
                if sha256(partial) != summary["sha256"]:
                    raise RuntimeError(f"Downloaded archive hash mismatch: {name}")
                partial.rename(output)
                for marker in markers.iterdir():
                    marker.unlink()
                markers.rmdir()
            manifest = fetch_bytes(summary["manifest"])
            assert hashlib.sha256(manifest).hexdigest() == summary["manifest_sha256"]
            (args.destination / summary["manifest"]).write_bytes(manifest)
            summary_name = name.replace(".tar.gz", ".summary.json")
            (args.destination / summary_name).write_text(json.dumps(summary, indent=2) + "\n")
            verified.add(name)
            print("VERIFIED_DOWNLOAD", name, summary["archive_bytes"], flush=True)
        if state["complete"]:
            index_name = args.prefix + "-index.json"
            index = fetch_bytes(index_name)
            expected = {s["archive"] for s in json.loads(index)["archives"]}
            if expected <= verified:
                (args.destination / index_name).write_bytes(index)
                print("ALL_DOWNLOADS_VERIFIED", len(verified), flush=True)
                break
        time.sleep(10)


if __name__ == "__main__":
    main()
