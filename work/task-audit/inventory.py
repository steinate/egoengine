"""Check every upstream task configuration without conflating preflight with simulation."""

import argparse, ast, collections, json, re
from pathlib import Path
import yaml

p = argparse.ArgumentParser()
p.add_argument("repo", type=Path)
p.add_argument("output", type=Path)
a = p.parse_args()
repo = a.repo.resolve()
base = repo / "workflows/simbox/core/configs/tasks"
registered = {}
for path in (repo / "workflows/simbox/core/skills").glob("*.py"):
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.ClassDef) and any(
            isinstance(d, ast.Name) and d.id == "register_skill" for d in node.decorator_list
        ):
            key = "_".join(re.sub(r"([A-Z0-9])", r" \1", node.name).split()).lower()
            registered[key] = str(path.relative_to(repo))


def walk(value):
    if isinstance(value, dict):
        yield value
        for v in value.values():
            yield from walk(v)
    elif isinstance(value, list):
        for v in value:
            yield from walk(v)


rows = []
for path in sorted(base.rglob("*.yaml")):
    rel = path.relative_to(base)
    row = dict(
        config=str(rel),
        family="/".join(
            (
                rel.parts[0],
                rel.parts[2] if len(rel.parts) > 3 else re.sub(r"_part\d+$", "", rel.stem),
            )
        )
        if len(rel.parts) > 2
        else str(rel.parent),
        embodiment=rel.parts[1] if len(rel.parts) > 2 else "example",
    )
    try:
        cfg = yaml.safe_load(path.read_text())
        row["has_fluid"] = any(bool(task.get("fluid")) for task in cfg["tasks"])
        row["object_classes"] = sorted(
            {
                obj.get("target_class", "")
                for task in cfg["tasks"]
                for obj in task.get("objects", [])
            }
        )
        missing_code = []
        missing_assets = []
        assets = []
        skills = []
        random_pools = []
        configs = {str(path): cfg}
        for task in cfg["tasks"]:
            root = repo / task["asset_root"]
            objects = list(task.get("objects", []))
            row["task_dir"] = task.get("data", {}).get("task_dir")
            row["instruction"] = task.get("data", {}).get("language_instruction")
            for node in walk(task.get("skills", [])):
                if "name" in node and ("objects" in node or node["name"] in registered):
                    skills.append(node["name"])
            pending = [cfg]
            seen = {str(path)}
            while pending:
                current = pending.pop()
                for node in walk(current):
                    for key in ["arena_file", "robot_config_file", "camera_file"]:
                        if key in node:
                            target = repo / node[key]
                            if str(target) in seen:
                                continue
                            seen.add(str(target))
                            if not target.is_file():
                                missing_code.append(node[key])
                                continue
                            sub = yaml.safe_load(target.read_text())
                            configs[str(target)] = sub
                            pending.append(sub)
                            if key == "arena_file":
                                objects += sub.get("fixtures", [])
                            if key == "robot_config_file":
                                objects.append(sub)
                            for f in sub.get("robot_file", []):
                                if not (repo / f).is_file():
                                    missing_assets.append(f)
            annotations = collections.defaultdict(set)
            for skill in walk(task.get("skills", [])):
                kind = skill.get("name")
                if kind in ["pick", "dexpick", "fail_pick", "manualpick", "dynamicpick"]:
                    for name in skill.get("objects", [])[:1]:
                        annotation = (
                            "dexpick_pose.yaml"
                            if kind == "dexpick"
                            else skill.get("npy_name", "Aligned_grasp_sparse.npy")
                        )
                        annotations[name].add(annotation)
            randomized = set()
            for obj in objects:
                if obj.get("apply_randomization") and obj.get("target_class") == "RigidObject":
                    name = obj["name"]
                    randomized.add(name)
                    category = (root / obj["path"]).parent.parent
                    scope = obj.get("randomization_scope", "category")
                    patterns = (
                        [category / "*/*.usd"]
                        if scope == "category"
                        else [category.parent / "*/*/*.usd"]
                        if scope == "full"
                        else [category.parent / c / "*/*.usd" for c in scope]
                    )
                    patterns = [str(v.relative_to(repo)) for v in patterns]
                    pool = dict(
                        object=name, patterns=patterns, annotations=sorted(annotations[name])
                    )
                    random_pools.append(pool)
                    candidates = [v for pattern in patterns for v in repo.glob(pattern)]
                    valid = [
                        v
                        for v in candidates
                        if all(
                            v.with_name(annotation).is_file() for annotation in annotations[name]
                        )
                    ]
                    if not valid:
                        missing_assets.append("random_pool:" + name)
                    continue
                if obj.get("target_class") == "ArticulatedObject" and obj.get(
                    "apply_randomization"
                ):
                    randomized.add(obj["name"])
                    pool = root / obj.get("art_cat", "")
                    if not any(
                        v.parent.parent.parent.joinpath("instance.usd").is_file()
                        for v in pool.glob("*/Kps/" + obj.get("info_name", "") + "/info.json")
                    ):
                        missing_assets.append(
                            str(pool.relative_to(repo))
                            + "/[instance]/Kps/"
                            + obj.get("info_name", "")
                            + "/info.json"
                        )
                    continue
                for key in ["path", "obj_info_path"]:
                    value = obj.get(key)
                    if not isinstance(value, str) or not value or "${" in value:
                        continue
                    target = root / value
                    assets.append(
                        str(target.relative_to(repo))
                        if target.is_relative_to(repo)
                        else str(target)
                    )
                    if not target.is_file():
                        missing_assets.append(assets[-1])
            byname = {x["name"]: x for x in task.get("objects", [])}
            for name, required in annotations.items():
                if name in randomized:
                    continue
                usd = byname.get(name, {}).get("path", "")
                if usd.endswith("Aligned_obj.usd"):
                    for annotation in required:
                        target = (root / usd).with_name(annotation)
                        if not target.is_file():
                            missing_assets.append(str(target.relative_to(repo)))
        unresolved = sorted(set(skills) - set(registered))
        row.update(
            skills=sorted(set(skills)),
            missing_skills=unresolved,
            missing_code=sorted(set(missing_code)),
            missing_assets=sorted(set(missing_assets)),
            assets=sorted(set(assets)),
            random_pools=random_pools,
        )
        row["status"] = (
            "blocked_source"
            if unresolved or missing_code
            else "blocked_assets"
            if missing_assets
            else "ready_for_runtime"
        )
    except Exception as error:
        row.update(status="invalid_config", error=repr(error))
    rows.append(row)
a.output.parent.mkdir(parents=True, exist_ok=True)
result = dict(
    scope="Every YAML checked; ready_for_runtime is NOT a successful simulation. Asset checks cover direct references and official rigid/articulated randomization pools, not all USD transitive dependencies.",
    configs=len(rows),
    status_counts=dict(collections.Counter(x["status"] for x in rows)),
    families=len(set(x["family"] for x in rows)),
    registered_skills=registered,
    rows=rows,
)
a.output.write_text(json.dumps(result, indent=2))
print(
    json.dumps(
        {k: v for k, v in result.items() if k not in ["rows", "registered_skills"]}, indent=2
    )
)
