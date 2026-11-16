"""Create private, content-verified migration archives without following symlinks."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import tarfile
import time


class HashedReader:
    def __init__(self, stream):
        self.stream = stream
        self.digest = hashlib.sha256()

    def read(self, size=-1):
        data = self.stream.read(size)
        self.digest.update(data)
        return data


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for data in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(data)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--prefix", default="deployment")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--exclude-name", action="append", default=[])
    parser.add_argument("--single-archive", help="Pack all children into one named component")
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output.resolve()
    if output == root or root in output.parents:
        parser.error("Output must be outside the source tree")
    output.mkdir(parents=True, exist_ok=True)
    exclude = set(args.exclude_name)
    children = sorted(p for p in root.iterdir() if p.name not in exclude)
    groups = [(p.name, [p]) for p in children if p.is_dir() and not p.is_symlink()]
    groups.append(("root-files", [p for p in children if not p.is_dir() or p.is_symlink()]))
    if args.single_archive:
        groups = [(args.single_archive, children)]

    def pack(group):
        name, paths = group
        archive = output / f"{args.prefix}-{name}.tar.gz"
        manifest = output / f"{args.prefix}-{name}.files.jsonl"
        summary = output / f"{args.prefix}-{name}.summary.json"
        if summary.exists():
            raise RuntimeError(f"Refusing to overwrite completed snapshot: {summary}")
        count = total = 0
        start = time.time()
        with tarfile.open(str(archive) + ".partial", "w:gz", compresslevel=1) as tar:
            with Path(str(manifest) + ".partial").open("w") as records:

                def add(path):
                    nonlocal count, total
                    if path.name in exclude:
                        return
                    relative = str(path.relative_to(root))
                    info = tar.gettarinfo(str(path), arcname=f"{args.prefix}/{relative}")
                    record = {"path": relative, "mode": info.mode, "size": info.size}
                    if info.isfile():
                        before = path.stat()
                        with path.open("rb") as source:
                            reader = HashedReader(source)
                            tar.addfile(info, reader)
                        after = path.stat()
                        if (before.st_size, before.st_mtime_ns) != (
                            after.st_size,
                            after.st_mtime_ns,
                        ):
                            raise RuntimeError(f"File changed during snapshot: {path}")
                        record.update(type="file", sha256=reader.digest.hexdigest())
                        total += info.size
                    elif info.isdir():
                        tar.addfile(info)
                        record["type"] = "directory"
                    elif info.issym():
                        tar.addfile(info)
                        record.update(type="symlink", target=info.linkname)
                    elif info.islnk():
                        tar.addfile(info)
                        record.update(type="hardlink", target=info.linkname)
                    else:
                        raise RuntimeError(f"Unsupported special file: {path}")
                    records.write(json.dumps(record, ensure_ascii=True) + "\n")
                    count += 1
                    if info.isdir():
                        for child in sorted(path.iterdir()):
                            add(child)

                for path in paths:
                    add(path)
        Path(str(archive) + ".partial").rename(archive)
        Path(str(manifest) + ".partial").rename(manifest)
        result = {
            "archive": archive.name,
            "sha256": sha256(archive),
            "manifest": manifest.name,
            "manifest_sha256": sha256(manifest),
            "entries": count,
            "uncompressed_file_bytes": total,
            "archive_bytes": archive.stat().st_size,
            "elapsed_s": round(time.time() - start, 1),
        }
        summary.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result), flush=True)
        return result

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        summaries = list(pool.map(pack, groups))
    index = {
        "source_root": str(root),
        "prefix": args.prefix,
        "excluded_names": sorted(exclude),
        "archives": summaries,
        "created_unix": time.time(),
    }
    (output / f"{args.prefix}-index.json").write_text(json.dumps(index, indent=2) + "\n")
    print("SNAPSHOT_COMPLETE", args.prefix, flush=True)


if __name__ == "__main__":
    main()
