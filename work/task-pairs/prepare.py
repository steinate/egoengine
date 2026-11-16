"""Prepare isolated official task variants; keep every adjustment explicit."""

import argparse
import json
from pathlib import Path
import yaml

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("root", type=Path)
p.add_argument("repo", type=Path)
p.add_argument("task")
p.add_argument("--seed", type=int, default=42)
p.add_argument("--tag", default="")
a = p.parse_args()
catalog = json.loads(Path(__file__).with_name("catalog.json").read_text())
entry = catalog["tasks"][a.task]
assert not a.tag or a.tag.replace("-", "").isalnum()
out = a.root.resolve() / "task-pairs" / a.task / (f"seed-{a.seed}" + ("-" + a.tag if a.tag else ""))
out.mkdir(parents=True, exist_ok=True)
assert not (out / "result.json").exists(), "Use another seed or trial directory"
cfg_path = a.repo / "workflows/simbox/core/configs/tasks" / entry["config"]
cfg = yaml.safe_load(cfg_path.read_text())
task = cfg["tasks"][0]
changes = [
    "Fixed asset instances to limit downloads; retained official skills and layout sampling.",
    "640x360 head and 320x240 wrist cameras with scaled intrinsics; RGB only.",
    "Record every physics step independently; append 30-step final stability observation.",
    "One explicit PhysX simulate(dt) call after task pre_step, with timeline paused for rendering; retain raw Isaac callback counters separately.",
    "Deactivate unused PhysicsScene imported by robot USD after checking it has no simulationOwner references; avoids duplicate Isaac clock callbacks.",
    "Raise max episode steps to at least 2000 without changing skill commands.",
]
for obj in task["objects"]:
    obj["apply_randomization"] = False
    if obj["target_class"] == "ArticulatedObject":
        prefix = "art/microwave_gr/microwave7119"
        obj.update(
            path=prefix + "/instance.usd",
            category="microwave_gr",
            obj_info_path=prefix + "/Kps/close_v/info.json",
            euler=[0, 0, 90],
        )
        info = json.loads(
            (a.root / "assets/InternDataAssets/assets" / obj["obj_info_path"]).read_text()
        )
        obj["scale"] = info["object_scale"][:3]
if "distractors" in task:
    task.pop("distractors")
    changes.append("Omitted optional distractors for debugging.")
for camera in task["cameras"]:
    camera_cfg = yaml.safe_load((a.repo / camera["camera_file"]).read_text())
    camera_cfg["resolution_width"] //= 2
    camera_cfg["resolution_height"] //= 2
    camera_cfg["camera_params"] = [x / 2 for x in camera_cfg["camera_params"]]
    camera_cfg.update(with_distance=False, depth=False, with_semantic=False)
    dest = out / (camera["name"].replace("${tasks.0.robots.0.name}", "robot") + ".yaml")
    dest.write_text(yaml.safe_dump(camera_cfg))
    camera["camera_file"] = str(dest)
task["data"]["collect_info"] = "paired-debug"
task["data"]["max_episode_length"] = max(task["data"]["max_episode_length"], 2000)
(out / "task.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
pipeline = yaml.safe_load((a.repo / "configs/simbox/de_plan_with_render_template.yaml").read_text())
pipeline["load_stage"]["scene_loader"]["args"]["cfg_path"] = str(out / "task.yaml")
pipeline["load_stage"]["layout_random_generator"]["args"].update(random_num=1, strict_mode=False)
pipeline["store_stage"]["writer"]["args"].update(
    output_dir=str(out / "official-output"), batch_async=False
)
(out / "pipeline.yaml").write_text(yaml.safe_dump(pipeline, sort_keys=False))
(out / "task-provenance.json").write_text(
    json.dumps(
        dict(entry, seed=a.seed, adjustments=changes, upstream_config=str(cfg_path)), indent=2
    )
)
print(out)
