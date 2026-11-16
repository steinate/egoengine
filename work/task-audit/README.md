# 官方任务覆盖与数据可重放性审计

本目录检验保留的 InternDataEngine 源码，不把 YAML 数量当成数据集任务数量，也不把一次规划失败当成该任务不可实现。

## 三个不同的覆盖范围

- InternData-A1 论文报告 70 个语义任务；同一任务可以有多种机器人、手臂、物体和分阶段版本。
- 上游基线 `2a0a21f2c836df97c925729084e13d68950b4deb` 包含 1128 个任务 YAML：art 59、basic 61、long_horizon 68、pick_and_place 939、example 1。按源码目录归并得到 59 个任务族，包含别名和示例，**不是论文 70 项的一一映射**。
- `inventory.py` 静态检查全部配置；`run_families.py` 每个源码任务族选择一个原始配置，调用官方规划 API。未逐一运行全部物体、机器人和左右臂变体。通过规划仍不等于通过物理终态、视频或人体接触验收。

最初只使用已有资产的 25 个配置测试保存在 `runtime-results.json`；补齐代表任务资产后的测试保存在 `family-runtime-results.json`。正式结论见仓库 `evidence/task-audit/` 中的报告与逐项结果。

## 在已部署工作区执行

先按根 README / `migration/FRESH_EPISODE.md` 安装 Isaac Sim 4.1、cuRobo、Drake 和基础场景。以下命令只在新服务器的同一工作区运行，不需要旧机器上的资产包。

```bash
workspace=/mnt/data/pengjiaqi/egoengine-workspace
repo="$workspace/egoengine"
audit="$workspace/run/task-audit"
mkdir -p "$audit"
cp "$repo"/work/task-audit/*.py "$audit/"

# 列出每份 YAML 的源码、技能、资产和随机化池依赖。
bash "$workspace/run/human41/usd_python.sh" "$audit/inventory.py" \
  "$repo" "$audit/inventory.json"

# 读取 HF 目录元数据及有大小上限的真实样本前缀，不下载完整数据集压缩包。
# 需先在 HF 接受数据集条款；私密 token 放 workspace/config/hf_token，chmod 600。
# 此脚本使用 hf-mirror.com；仅在授权向该镜像发送 token 后执行。
bash "$workspace/run/human41/usd_python.sh" "$audit/hf_probe.py" "$workspace"

# 查询需要的资产目录，选择每个任务族依赖体积最小的代表配置。
bash "$workspace/run/human41/usd_python.sh" "$audit/asset_index.py" "$workspace"
bash "$workspace/run/human41/usd_python.sh" "$audit/family_assets.py" "$workspace"
# 先检查 family-assets.json：选择的配置、文件数量、additional_bytes 和 unresolved。
bash "$workspace/run/human41/usd_python.sh" "$audit/download_family_assets.py" "$workspace"
# 仅下载清单中缺少的文件；已有同大小文件仍校验 hash，不覆盖不同文件。
bash "$workspace/run/human41/usd_python.sh" "$audit/download_family_assets.py" \
  "$workspace" --download --workers 4

bash "$workspace/run/human41/usd_python.sh" "$audit/inventory.py" \
  "$repo" "$audit/inventory-final.json"
bash "$workspace/run/human41/usd_python.sh" "$audit/run_families.py" "$workspace" --timeout 300
```

`family_assets.py` 尊重官方 rigid/articulated 随机化池；配置中不存在的默认实例，在 `apply_randomization: true` 时不一定是阻塞。每个池需要至少一个有效 USD 及相应抓取标注；`dexpick` 需要 `dexpick_pose.yaml`，普通 `pick` 通常需要 `Aligned_grasp_sparse.npy`。最小资产集合会改变可采样实例范围，因此结果只代表该受限资产集合。预检不保证所有 USD 嵌套纹理、外部引用或控制器资源齐全，实际加载结果单独记录。

测试依次调用原配置的 `init_task → randomization → generate_seq`；流体配置使用官方要求的 `plan_with_render`。这是官方工作流 API 测试，不是完整 Nimbus 分布式 launcher 测试。每个配置独立进程、默认 seed 43，共享 GPU 文件锁，超时终止当前进程组。已有完成结果复用，需重新测试时换输出目录并保留原结果。

每次尝试保存：

- `result.json`：阶段、状态、seed、耗时、异常；新版 runner 另保存配置/runner SHA-256 和 engine commit。
- `stdout.log` / `kit.log`：初始化、规划和仿真日志。
- `resolved-task.json`：成功随机化后实际布局、资产实例和任务配置。
- 成功规划的 `official-plan.pkl`：官方 `dump_plan_info()`，包含配置、WorldRecorder 和 logger；`scene.usdc` 为场景层导出，仍需原资产引用。

`planning_succeeded` 只表示官方 API 返回非零帧数；`planning_failed` 是该 seed 未通过；`runtime_error`、`timeout`、依赖阻塞分别报告。源代码缺失、资产缺失、随机布局失败不能混为算法失败。少量随机种子不能证明一项任务不可实现。

## 已发布机器人数据能否直接生成对应 Human ego

对 `sim_updated/articulation_tasks/franka/close_the_washingmachine_left.tar.gz` 只取最多 16 MiB 压缩前缀，读取其中真实 Parquet 的 Hugging Face schema 元数据。该样本包含机器人关节、夹爪、TCP/末端位姿、相机参数和时间戳，**没有完整物体/连杆世界位姿、场景布局与资产实例**。五个官方 A1 LeRobot converter 的 FEATURES 也没有完整的物体状态字段。证据保存为 `actual-parquet-metadata.json` 和 `converter-schemas.json`。

所以必须区分：

1. **重新生成配对数据**：从官方任务配置规划新的机器人 episode，同时记录完整场景状态；人体 IK 使用其物体接触轨迹，固定眼位重放。这条路线已验收挂杯、关闭微波炉、插花三项，参见 `work/task-pairs/README.md`。
2. **逐条对应已发布 HF episode**：需要与该 episode 匹配的原始 plan / WorldRecorder / 含物体状态的原始日志及场景。仅用上述 LeRobot schema 里的机器人状态，不能唯一确定物体是否滑动、被放置到何处，以及门的运动。重新运行同名任务不会恢复同一条发布轨迹。

这不是声称所有 HF 压缩包都没有额外原始数据；检查范围是实际抽样文件、公开目录及官方转换器。还没有找到足以严格重放所有已发布 episode 的逐条场景状态来源。

精确重放的最小输入约定：

| 输入 | 必需内容 |
|---|---|
| 场景 | 原 USD/资产标识、文件 hash、实例尺寸、坐标系、初始布局与随机化配置 |
| 时间 | 每帧 timestamp、实际物理 dt、帧索引；与机器人视频逐帧对应 |
| 刚体/关节物体 | 物体根与所有活动连杆的世界变换、关节状态、可见性 |
| 机器人与交互 | 关节、TCP、夹爪开合、技能/接触/释放事件 |
| 原相机 | 外参、内参及变动时间，用于验证原视频重放 |
| 非刚体/视觉变化 | 液体粒子、布料顶点或形变缓存、污渍/材质/可见性随时间变化 |

当前刚体位姿记录和人体重放不覆盖最后一行。官方 `plan_with_render` 的流体成功也不能自动成为完整粒子重放数据；必须另加逐步缓存并验证。

源码名称、data.task_dir 和语言指令的检查尚未找到折衣/折毛巾、炉灶旋钮、扫垃圾、识价取物、选饮料、扫码等部分发布任务的完整对应配置。因此不能承诺公开仓库可完整复现论文全部 70 项。通用技能可能实现这些任务，需补任务配置与专门验收，不能当成现成例子。

来源：[官方数据集](https://huggingface.co/datasets/InternRobotics/InternData-A1)、[论文](https://arxiv.org/html/2511.16651v1)、[官方 quickstart（含流体模式要求）](https://internrobotics.github.io/InternDataEngine-Docs/guides/quickstart.html)、[安装说明](https://internrobotics.github.io/InternDataEngine-Docs/guides/installation.html)。
