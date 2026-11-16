"""Verify and restore an offline snapshot into a new directory without overwrites."""

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import tarfile

from build_snapshot import sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--prefix", default="deployment")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    args.destination = args.destination.resolve()
    index = json.loads((args.bundle / f"{args.prefix}-index.json").read_text())
    for item in index["archives"]:
        for name, digest in [
            (item["archive"], item["sha256"]),
            (item["manifest"], item["manifest_sha256"]),
        ]:
            assert Path(name).name == name, name
            path = args.bundle / name
            assert sha256(path) == digest, f"Hash mismatch: {path}"
        print("ARCHIVE_OK", item["archive"], flush=True)
    if args.verify_only:
        print("ALL_ARCHIVES_VERIFIED", flush=True)
        return
    if args.destination.exists():
        parser.error("Destination already exists; use a new empty location")
    args.destination.mkdir(parents=True)
    directories = []
    count = 0
    for item in index["archives"]:
        records = {}
        for line in (args.bundle / item["manifest"]).read_text().splitlines():
            record = json.loads(line)
            records[record["path"]] = record
        seen = set()
        with tarfile.open(args.bundle / item["archive"], "r|gz") as archive:
            for member in archive:
                p = PurePosixPath(member.name)
                assert not p.is_absolute() and ".." not in p.parts, member.name
                assert p.parts[0] == args.prefix, member.name
                relative = str(PurePosixPath(*p.parts[1:]))
                record = records[relative]
                assert relative not in seen, relative
                seen.add(relative)
                output = args.destination / relative
                assert not any(parent.is_symlink() for parent in output.parents), output
                if member.isdir():
                    output.mkdir(parents=True, exist_ok=True)
                    directories.append((output, member.mode))
                elif member.issym():
                    assert member.linkname == record["target"], relative
                    output.symlink_to(member.linkname)
                elif member.islnk():
                    target = PurePosixPath(member.linkname)
                    assert target.parts[0] == args.prefix and ".." not in target.parts
                    os.link(args.destination.joinpath(*target.parts[1:]), output)
                elif member.isfile():
                    import hashlib

                    digest = hashlib.sha256()
                    stream = archive.extractfile(member)
                    with output.open("xb") as destination:
                        for data in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                            destination.write(data)
                            digest.update(data)
                    assert output.stat().st_size == record["size"], relative
                    assert digest.hexdigest() == record["sha256"], relative
                    output.chmod(member.mode)
                    os.utime(output, (member.mtime, member.mtime))
                else:
                    raise RuntimeError(f"Unsupported archive entry: {member.name}")
                count += 1
        assert seen == records.keys(), item["archive"]
        print("RESTORED_AND_HASHED", item["archive"], len(seen), flush=True)
    for directory, mode in reversed(directories):
        directory.chmod(mode)
    print("RESTORE_VERIFIED", count, "entries", args.destination, flush=True)


if __name__ == "__main__":
    main()
