"""Inventory published assets and size required missing files; metadata only."""

import argparse, json, time, urllib.request, urllib.parse
from pathlib import Path
from dataset_revision import pinned_revision

p = argparse.ArgumentParser()
p.add_argument("workspace", type=Path)
p.add_argument(
    "--inventory",
    type=Path,
    help="Use a later preflight without overwriting the baseline inventory",
)
a = p.parse_args()
w = a.workspace
b = w / "run/task-audit"
out = b / "hf/asset-tree.json"
token = (w / "config/hf_token").read_text().strip()
revision = pinned_revision(b / "hf", token)
endpoint = "https://hf-mirror.com"
repo = "InternRobotics/InternData-A1"
inventory_path = a.inventory or b / "inventory.json"
rows = json.loads(inventory_path.read_text())["rows"]
scopes = sorted(
    {
        path.split("/")[3]
        for row in rows
        for path in (
            row.get("missing_assets", [])
            + [pattern for pool in row.get("random_pools", []) for pattern in pool["patterns"]]
            + [pool["directory"] for pool in row.get("texture_pools", [])]
        )
        if path.startswith("workflows/simbox/assets/") and len(path.split("/")) > 3
    }
)
items = []
for scope in scopes:
    cached = b / "hf" / ("asset-scope-" + scope + ".json")
    if cached.exists():
        items.extend(json.loads(cached.read_text()))
        continue
    url = f"{endpoint}/api/datasets/{repo}/tree/{revision}/InternDataAssets/assets/{scope}?recursive=true&limit=1000"
    page = 0
    scope_items = []
    while url:
        for attempt in range(4):
            try:
                req = urllib.request.Request(url)
                req.add_unredirected_header("Authorization", "Bearer " + token)
                with urllib.request.urlopen(req, timeout=60) as r:
                    data = json.load(r)
                    link = r.headers.get("Link", "")
                break
            except urllib.error.HTTPError as error:
                if error.code == 404:
                    data, link = [], ""
                    break
                if attempt == 3:
                    raise
                time.sleep(2**attempt)
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(2**attempt)
        scope_items.extend(data)
        page += 1
        url = link.split(">;")[0].lstrip("<") if 'rel="next"' in link else None
        if url:
            u = urllib.parse.urlsplit(url)
            assert u.hostname in ["huggingface.co", "hf-mirror.com"]
            url = endpoint + u.path + ("?" + u.query if u.query else "")
        print("METADATA_PAGE", scope, page, len(scope_items), flush=True)
    cached.write_text(json.dumps(scope_items))
    items.extend(scope_items)
out.write_text(json.dumps(items))
lookup = {x["path"]: x for x in items if x["type"] == "file"}
rows = json.loads(inventory_path.read_text())["rows"]
needed = {}
for row in rows:
    for path in row.get("missing_assets", []):
        if not path.startswith("workflows/simbox/assets/") or "[" in path:
            continue
        rel = "InternDataAssets/assets/" + path.removeprefix("workflows/simbox/assets/")
        item = needed.setdefault(rel, dict(path=rel, configs=[], published=rel in lookup))
        item["configs"].append(row["config"])
for rel, item in needed.items():
    if rel in lookup:
        item["bytes"] = lookup[rel]["size"]
        item["sha256"] = lookup[rel].get("lfs", {}).get("oid")
        item["url"] = (
            "https://huggingface.co/datasets/"
            + repo
            + "/resolve/"
            + revision
            + "/"
            + urllib.parse.quote(rel, safe="/")
        )
result = dict(
    scope="Direct missing references only; textures, USD dependencies and randomization pools add more files.",
    published_asset_files_in_scopes=len(lookup),
    queried_scopes=scopes,
    missing_references=len(needed),
    known_direct_bytes=sum(x.get("bytes", 0) for x in needed.values()),
    unpublished_direct_paths=sum(not x["published"] for x in needed.values()),
    files=list(needed.values()),
)
(b / "missing-asset-downloads.json").write_text(json.dumps(result, indent=2))
print("ASSET_INDEX_DONE", {k: v for k, v in result.items() if k != "files"}, flush=True)
