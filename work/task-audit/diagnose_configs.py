"""Locate specific configuration failures observed during real task execution."""

import argparse
import json
from pathlib import Path
import yaml

p = argparse.ArgumentParser()
p.add_argument("repo", type=Path)
p.add_argument("output", type=Path)
a = p.parse_args()
root = a.repo / "workflows/simbox/core/configs/tasks"
findings = []


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


for file in sorted(root.rglob("*.yaml")):
    for task in yaml.safe_load(file.read_text())["tasks"]:
        for obj in task.get("objects", []):
            if (
                obj.get("target_class") == "ArticulatedObject"
                and not obj.get("apply_randomization")
                and not obj.get("obj_info_path")
            ):
                findings.append(
                    dict(
                        config=str(file.relative_to(root)),
                        issue="empty_static_articulation_info",
                        object=obj["name"],
                        meaning="ArticulatedObject opens asset_root as a file when obj_info_path is empty.",
                    )
                )
        for node in walk(task.get("skills", [])):
            if (
                node.get("name") == "place"
                and node.get("place_direction", "vertical") == "horizontal"
                and "offset_place_obj_axis" not in node
            ):
                findings.append(
                    dict(
                        config=str(file.relative_to(root)),
                        issue="missing_horizontal_offset_axis",
                        position_constraint=node.get("position_constraint", "gripper"),
                        meaning="Place.sample_gripper_place_traj unconditionally reads offset_place_obj_axis even though only the object-constrained branch uses it.",
                    )
                )
a.output.parent.mkdir(parents=True, exist_ok=True)
a.output.write_text(json.dumps(findings, indent=2))
print(json.dumps(findings, indent=2))
