"""Plan the smallest available asset subset for one representative of each source task family."""

import argparse, collections, fnmatch, json
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("workspace", type=Path)
a = p.parse_args()
w = a.workspace
b = w / "run/task-audit"
repo = w / "egoengine"
root = w / "run/assets"
rows = json.loads((b / "inventory.json").read_text())["rows"]
entries = json.loads((b / "hf/asset-tree.json").read_text())
lookup = {x["path"]: x for x in entries if x["type"] == "file"}
base = "InternDataAssets/assets/"


def relevant(item):
    name = Path(item["path"]).name.lower()
    return (
        not name.endswith((".obj", ".mtl", ".blend", ".fbx", ".zip", ".tar.gz"))
        and "copy" not in name
    )


prefix_cache = {}


def prefix_files(prefix):
    if prefix not in prefix_cache:
        prefix_cache[prefix] = [
            x for k, x in lookup.items() if k.startswith(prefix + "/") and relevant(x)
        ]
    return prefix_cache[prefix]


existing = {}


def present(item):
    name = item["path"]
    if name not in existing:
        target = root / name
        existing[name] = target.is_file() and target.stat().st_size == item["size"]
    return existing[name]


def missing_cost(items):
    return sum(x["size"] for x in items if not present(x))


def dependencies(row):
    prefixes = []
    unresolved = []
    for name in row.get("missing_assets", []):
        if name.startswith("random_pool:"):
            pool = next(x for x in row["random_pools"] if x["object"] == name.split(":", 1)[1])
            patterns = [
                base + pattern.removeprefix("workflows/simbox/assets/")
                for pattern in pool["patterns"]
                if pattern.startswith("workflows/simbox/assets/")
            ]
            matches = [
                k
                for k in lookup
                if any(
                    fnmatch.fnmatchcase(k, pattern) and k.count("/") == pattern.count("/")
                    for pattern in patterns
                )
                and all(
                    str(Path(k).with_name(annotation)) in lookup
                    for annotation in pool["annotations"]
                )
            ]
            if not matches:
                unresolved.append(name + " " + str(pool["patterns"]))
                continue
            prefixes.append(
                min(
                    (str(Path(k).parent) for k in matches),
                    key=lambda x: missing_cost(prefix_files(x)),
                )
            )
            continue
        if not name.startswith("workflows/simbox/assets/"):
            unresolved.append(name)
            continue
        rel = base + name.removeprefix("workflows/simbox/assets/")
        if "[instance]" in rel:
            matches = [k for k in lookup if fnmatch.fnmatchcase(k, rel.replace("[instance]", "*"))]
            if not matches:
                unresolved.append(name)
                continue
            candidates = [k.split("/Kps/")[0] for k in matches]
            prefix = min(candidates, key=lambda x: missing_cost(prefix_files(x)))
        elif rel in lookup:
            prefix = str(Path(rel).parent)
            # An info file belongs to its model, including the root USD.
            if "/Kps/" in prefix:
                prefix = prefix.split("/Kps/")[0]
        else:
            unresolved.append(name)
            continue
        prefixes.append(prefix)
    files = {x["path"]: x for prefix in prefixes for x in prefix_files(prefix)}
    return list(files.values()), unresolved


families = collections.defaultdict(list)
for row in rows:
    families[row["family"]].append(row)
selected = []
allfiles = {}
for family, candidates in sorted(families.items()):
    ranked = []
    for row in candidates:
        files, unresolved = dependencies(row)
        blocked = row.get("missing_code", []) + row.get("missing_skills", []) + unresolved
        if row["status"] == "invalid_config":
            blocked.append(row.get("error", "invalid_config"))
        ranked.append(((bool(blocked), missing_cost(files), row["config"]), row, files, blocked))
    _, row, files, blocked = min(ranked, key=lambda x: x[0])
    item = dict(
        family=family,
        config=row["config"],
        embodiment=row["embodiment"],
        status="blocked" if blocked else "existing_assets" if not files else "downloadable",
        missing_bytes=missing_cost(files),
        unresolved=blocked,
        files=[x["path"] for x in files],
    )
    selected.append(item)
    if not blocked:
        allfiles.update({x["path"]: x for x in files})
manifest = dict(
    scope="One representative per source task family; original skills/configs retained. Direct asset model directories, without redundant authoring files; USD transitive dependencies still checked at runtime.",
    families=len(selected),
    counts=dict(collections.Counter(x["status"] for x in selected)),
    additional_bytes=missing_cost(allfiles.values()),
    selected=selected,
    files=list(allfiles.values()),
)
(b / "family-assets.json").write_text(json.dumps(manifest, indent=2))
print(json.dumps({k: v for k, v in manifest.items() if k not in ["files", "selected"]}, indent=2))
for x in selected:
    print("FAMILY", x["family"], x["status"], x["missing_bytes"], x["unresolved"][:2], flush=True)
