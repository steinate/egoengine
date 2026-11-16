"""Read remote directory metadata and a bounded archive prefix, never a full dataset archive."""

import argparse, io, json, tarfile, urllib.request, struct, time
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("workspace", type=Path)
p.add_argument("--metadata-only", action="store_true")
p.add_argument(
    "--version", choices=["sim", "sim_updated", "sim_updated_lerobotv30"], default="sim_updated"
)
a = p.parse_args()
out = a.workspace / "run/task-audit/hf"
out.mkdir(parents=True, exist_ok=True)
token = (a.workspace / "config/hf_token").read_text().strip()
endpoint = "https://hf-mirror.com"
repo = "InternRobotics/InternData-A1"


def get(url, limit=None):
    req = urllib.request.Request(url)
    req.add_unredirected_header("Authorization", "Bearer " + token)
    if limit:
        req.add_header("Range", f"bytes=0-{limit - 1}")
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read(limit) if limit else r.read()
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2**attempt)


root = json.loads(get(f"{endpoint}/api/datasets/{repo}/tree/main?limit=1000"))
(out / "root-tree.json").write_text(json.dumps(root, indent=2))
print("ROOT", [(x["path"], x["type"]) for x in root], flush=True)
for version in ["sim", "sim_updated", "sim_updated_lerobotv30"]:
    if (out / (version + "-tree.json")).exists():
        continue
    entries = json.loads(
        get(f"{endpoint}/api/datasets/{repo}/tree/main/{version}?recursive=true&limit=1000")
    )
    assert len(entries) < 1000, "Directory index may be paginated"
    (out / (version + "-tree.json")).write_text(json.dumps(entries, indent=2))
    print("DATASET_INDEX", version, len(entries), flush=True)
if a.metadata_only:
    raise SystemExit(0)
if a.version != "sim_updated":
    out = out / a.version
    out.mkdir(exist_ok=True)
path = a.version + "/articulation_tasks/franka/close_the_washingmachine_left.tar.gz"
data = get(f"{endpoint}/datasets/{repo}/resolve/main/{path}", 16 * 1024 * 1024)
(out / "archive-prefix.bin").write_bytes(data)
members = []
try:
    with tarfile.open(fileobj=io.BytesIO(data), mode="r|gz") as tar:
        for item in tar:
            members.append(dict(name=item.name, size=item.size, type=str(item.type)))
            if (
                item.isfile()
                and (item.name.endswith(".json") or item.name.endswith(".parquet"))
                and item.size < 5 * 1024 * 1024
            ):
                payload = tar.extractfile(item).read()
                dest = out / Path(item.name).name
                dest.write_bytes(payload)
                print("EXTRACTED", item.name, len(payload), flush=True)
                if item.name.endswith(".parquet") and payload[-4:] == b"PAR1":
                    length = struct.unpack("<I", payload[-8:-4])[0]
                    footer = payload[-8 - length : -8]
                    start = footer.find(b'{"info":')
                    if start >= 0:
                        metadata, _ = json.JSONDecoder().raw_decode(
                            footer[start:].decode("utf8", errors="replace")
                        )
                        (out / "actual-parquet-metadata.json").write_text(
                            json.dumps(metadata, indent=2)
                        )
                    break
            if len(members) > 60:
                break
except (EOFError, tarfile.ReadError, OSError) as error:
    print("BOUNDED_PREFIX_END", type(error).__name__, flush=True)
(out / "archive-members.json").write_text(
    json.dumps(dict(archive=path, prefix_bytes=len(data), members=members), indent=2)
)
print("MEMBERS", members, flush=True)
