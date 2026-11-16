"""Build a compact, reviewable audit from actual inventory and runtime results."""

import argparse
import collections
import csv
import io
import hashlib
import json
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("audit", type=Path)
p.add_argument("output", type=Path)
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=True)
base = a.audit
inventory = json.loads((base / "inventory-final.json").read_text())
manifest = json.loads((base / "family-assets.json").read_text())
results = json.loads((base / "family-runtime-results.json").read_text())
by_config = {row["config"]: row for row in inventory["rows"]}
for result in results:
    config = by_config[result["config"]]
    family = result["family"]
    result["human_replay_requirement"] = (
        "需额外记录粒子/液体状态；当前刚体转换器不覆盖"
        if config.get("has_fluid")
        else "需核对污渍/可见性或材质变化，另适配工具接触"
        if "clean_the_dirt" in family
        else "需灵巧手接触及手指映射，尚未完成人体转换"
        if "dexpnp" in family
        else "已有同任务的独立配对验收 episode；本配置实例仍按本行结果判断"
        if family
        in [
            "basic/hang_the_cup_on_rack",
            "basic/insert_the_flower_in_vase",
            "art/close_the_microwave",
        ]
        else "候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收"
    )
initial = [r for r in json.loads((base / "runtime-results.json").read_text()) if r.get("run_dir")]
retests = []
for retest_file in sorted((base / "retests").glob("*/family-runtime-results.json")):
    retests.extend(json.loads(retest_file.read_text()))
attempts = [r for r in initial + results + retests if r.get("run_dir")]
successes_by_family = collections.defaultdict(list)
for attempt in attempts:
    if attempt["status"] == "planning_succeeded":
        successes_by_family[attempt["family"]].append(attempt["config"])
for result in results:
    result["successful_configs_across_all_attempts"] = successes_by_family[result["family"]]
assert len(results) == manifest["families"], "Do not label an incomplete batch complete"
assert {r["family"] for r in results} == {r["family"] for r in manifest["selected"]}


def write(name, value):
    (a.output / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


write("family-results.json", results)
write("retest-results.json", retests)
human_lines = [
    "# Human ego 转换候选与当前验证边界",
    "",
    "下表是按源码任务族整理的接入要求，不代表全部通过人体 IK 或视频验收。规划结果与配对验收分别保留。",
    "",
    "| 任务族 | 代表配置结果 | 其他实跑中成功的配置 | 人体重放要求 |",
    "|---|---|---|---|",
]
for result in results:
    human_lines.append(
        f"| {result['family']} | {result['status']} | {'; '.join(result['successful_configs_across_all_attempts'])} | {result['human_replay_requirement']} |"
    )
(a.output / "HUMAN_CANDIDATES.md").write_text("\n".join(human_lines) + "\n")
write("initial-runtime-results.json", initial)
if (base / "plan-integrity-results.json").exists():
    write(
        "plan-integrity-results.json",
        json.loads((base / "plan-integrity-results.json").read_text()),
    )
fields = [
    "config",
    "family",
    "embodiment",
    "status",
    "skills",
    "missing_code",
    "missing_assets",
    "has_fluid",
    "object_classes",
    "error",
]
f = io.StringIO()
c = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
c.writeheader()
for row in inventory["rows"]:
    c.writerow(
        {
            k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
            for k, v in row.items()
            if k in fields
        }
    )
(a.output / "all-configs.csv").write_text(f.getvalue())
files = []
for x in manifest["files"]:
    files.append(
        dict(
            path=x["path"],
            bytes=x["size"],
            hash_algorithm="sha256" if x.get("lfs") else "git_blob_sha1",
            hash=x.get("lfs", {}).get("oid", x["oid"]),
        )
    )
write(
    "asset-manifest.json",
    dict(
        repository="InternRobotics/InternData-A1",
        revision="main (resolved hashes below)",
        url_prefix="https://huggingface.co/datasets/InternRobotics/InternData-A1/resolve/main/",
        selected=manifest["selected"],
        files=files,
    ),
)
sample_receipts = []
for folder in [base / "hf", base / "hf/sim", base / "hf/sim_updated_lerobotv30"]:
    prefix = folder / "archive-prefix.bin"
    if prefix.exists():
        sample_receipts.append(
            dict(
                folder=str(folder.relative_to(base)),
                bytes=prefix.stat().st_size,
                sha256=hashlib.sha256(prefix.read_bytes()).hexdigest(),
            )
        )
        if folder != base / "hf" and (folder / "archive-members.json").exists():
            write(
                folder.name + "-archive-members.json",
                json.loads((folder / "archive-members.json").read_text()),
            )
write("sample-receipts.json", sample_receipts)
for name in ["actual-parquet-metadata.json", "archive-members.json"]:
    write(name, json.loads((base / "hf" / name).read_text()))
versions = {}
for version in ["sim", "sim_updated", "sim_updated_lerobotv30"]:
    entries = json.loads((base / "hf" / (version + "-tree.json")).read_text())
    fs = [x for x in entries if x["type"] == "file"]
    versions[version] = dict(files=len(fs), bytes=sum(x["size"] for x in fs))
summary = dict(
    upstream_baseline="2a0a21f2c836df97c925729084e13d68950b4deb",
    scope="Static checks on all YAMLs; one selected original configuration per source directory family; default seed 43. Not every embodiment/object variant, not all paper semantic tasks, not full physical/video validation.",
    configs=inventory["configs"],
    static_status_counts=inventory["status_counts"],
    source_families=manifest["families"],
    family_runtime_counts=dict(collections.Counter(r["status"] for r in results)),
    families_with_a_successful_attempt=len([v for v in successes_by_family.values() if v]),
    successful_configs_across_all_attempts=dict(successes_by_family),
    additional_retest_attempts=len(retests),
    retest_runtime_counts=dict(collections.Counter(r["status"] for r in retests)),
    initial_attempts=len(initial),
    initial_runtime_counts=dict(collections.Counter(r["status"] for r in initial)),
    unique_attempted_configs=len(
        {r["config"] for r in results + initial + retests if r.get("run_dir")}
    ),
    hf_published_versions=versions,
    sampled_parquet_columns=list(
        json.loads((base / "hf/actual-parquet-metadata.json").read_text())["info"]["features"]
    ),
    official_additional_pipeline=dict(
        discussion="https://huggingface.co/datasets/InternRobotics/InternData-A1/discussions/11",
        repository="https://github.com/InternRobotics/SIM1",
        scope="Official org reply points to InternDataEngine plus SIM1. SIM1 is a separate Newton/Warp cloth pipeline, not executed by this Isaac Sim 4.1 audit; the reply does not give episode-to-scene mappings.",
    ),
    exact_published_episode_replay="Not established: sampled released LeRobot schema and official converters omit complete scene/asset/object states.",
    verified_paired_tasks=["hang_cup", "close_microwave", "insert_flower"],
    paired_task_scope="New official-task episodes, original Worker, fixed eye/front cameras; complete source times and object states retained; debug rendering approximately 5 Hz.",
)
write("summary.json", summary)
for version in ["v1", "v2", "final"]:
    name = "family-asset-download-results" + ("-" + version if version != "final" else "") + ".json"
    if (base / name).exists():
        downloaded = json.loads((base / name).read_text())
        summary.setdefault("asset_downloads", {})[version] = dict(
            counts=dict(collections.Counter(x["status"] for x in downloaded)),
            downloaded_bytes=sum(x["bytes"] for x in downloaded if x["status"] == "downloaded"),
            failed=[x for x in downloaded if x["status"] == "failed"],
        )
write("summary.json", summary)
lines = [
    "# 本机官方任务复现审计",
    "",
    "测试范围：全部 1128 个 YAML 做依赖检查；59 个源码任务族各选一个原配置执行。没有逐一测试所有机器人、左右臂和物体变体。论文 70 个语义任务与源码目录任务族不是一一对应。",
    "",
    "## 实际执行结果",
    "",
    "```json",
    json.dumps(summary["family_runtime_counts"], indent=2),
    "```",
    "",
    "成功仅表示官方规划 API 返回非零帧数；失败仅表示本次 seed/资产集合未通过。完整物体轨迹、终态与人体视频另行验收，目前配对视频验证的是挂杯、关闭微波炉和插花三项。",
    "",
    "| 源码任务族 | 实际配置 | 状态 | 帧数 | 异常/阻塞 |",
    "|---|---|---|---:|---|",
]
for r in results:
    reason = r.get("error") or "; ".join(r.get("unresolved", []))
    lines.append(
        "| "
        + " | ".join(
            str(v).replace("|", "\\|").replace("\n", " ")
            for v in [r["family"], r["config"], r["status"], r.get("frames", ""), reason]
        )
        + " |"
    )
lines += [
    "",
    "## 能否重建 HF 已发布 episode",
    "",
    "抽样读取真实 Parquet，并检查官方 converter：有机器人动作/状态、相机、时间戳，没有完整场景资产与逐帧物体/连杆状态。因此目前能从现有官方任务重新生成配对 episode，不能据此宣称逐条精确复现已发布 HF 视频。需要与源 episode 匹配的原 plan/WorldRecorder、场景及资产。流体、布料和污渍还需要额外非刚体/材质状态缓存。",
    "",
    "当前 InternDataEngine 源码尚未找到折衣/毛巾、炉灶旋钮、扫垃圾、识价取物、选饮料、扫码等部分数据集任务的完整对应配置；未证明覆盖全部 70 项。",
    "",
    "官方在 [discussion #11](https://huggingface.co/datasets/InternRobotics/InternData-A1/discussions/11) 指向 InternDataEngine 与 [SIM1](https://github.com/InternRobotics/SIM1) 两套生成代码。SIM1 的 Newton/Warp 布料管线不在本次 Isaac Sim 4.1 测试内；这不等于布料代码完全未开源，也不能据此推断已发布 A1 episode 可以逐条精确重放。",
    "",
    "运行方式、状态定义和输入约定见 [审计说明](../../work/task-audit/README.md)。全部配置依赖结果见 [all-configs.csv](all-configs.csv)，真实 HF 样本字段见 [actual-parquet-metadata.json](actual-parquet-metadata.json)。",
    "",
    "来源：[数据集](https://huggingface.co/datasets/InternRobotics/InternData-A1)、[论文](https://arxiv.org/html/2511.16651v1)、[官方 Quickstart](https://internrobotics.github.io/InternDataEngine-Docs/guides/quickstart.html)。",
    "",
]
(a.output / "REPORT.md").write_text("\n".join(lines))
print(json.dumps(summary, indent=2, ensure_ascii=False))
