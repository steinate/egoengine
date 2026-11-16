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
bash "$workspace/run/human41/usd_python.sh" "$audit/test_inventory.py"
bash "$workspace/run/human41/usd_python.sh" "$audit/test_process_control.py"

# 列出每份 YAML 的源码、技能、资产和随机化池依赖。
bash "$workspace/run/human41/usd_python.sh" "$audit/inventory.py" \
  "$repo" "$audit/inventory.json"

# 读取 HF 目录元数据及有大小上限的真实样本前缀，不下载完整数据集压缩包。
# 需先在 HF 接受数据集条款；私密 token 放 workspace/config/hf_token，chmod 600。
# 此脚本使用 hf-mirror.com；仅在授权向该镜像发送 token 后执行。
bash "$workspace/run/human41/usd_python.sh" "$audit/hf_probe.py" "$workspace"
bash "$workspace/run/human41/usd_python.sh" "$audit/hf_probe.py" "$workspace" \
  --version sim_updated_lerobotv30 --prefix-mib 32
# 可选：直接核对已抽样 Parquet 的物理列结构；依赖、缓存均留在工作区。
bash "$workspace/run/human41/usd_python.sh" -m pip install --no-deps \
  --cache-dir "$workspace/run/cache41/pip" --target "$audit/python" pyarrow==17.0.0
bash "$workspace/run/human41/usd_python.sh" "$audit/check_parquet.py" "$audit"

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
bash "$workspace/run/human41/usd_python.sh" "$audit/run_families.py" "$workspace" --timeout 600
bash "$workspace/run/human41/usd_python.sh" "$audit/check_plans.py" "$audit"
bash "$workspace/run/human41/usd_python.sh" "$audit/diagnose_configs.py" \
  "$repo" "$audit/config-defects.json"
bash "$workspace/run/human41/usd_python.sh" "$audit/report.py" "$audit" "$audit/evidence"
```

`dataset_revision.py` 把本工作区固定到首次查询到的数据集 commit；目录查询和后续下载使用该 revision，并保留 LFS SHA-256 / Git blob SHA-1。实际验收资产版本是 `56450d831fff01a9091ccde5a8b68c103a775a60`。重新审计其他版本时使用新的审计目录，避免混用缓存。

若要使用本次相同的 59 份代表配置，可用 `evidence/task-audit/family-selection.json` 作为 `run/task-audit/family-assets.json`，替代重新运行 `family_assets.py` 的选择结果；它保留原始下载元数据，可直接用于下载器。用新的 `--tag` 保存复测，避免复用旧结果。固定配置和 seed 不保证恢复某条旧 episode 的场景；精确重放仍以原始 plan、实际布局与状态记录为准。

`family_assets.py` 尊重官方 rigid/articulated 随机化池；配置中不存在的默认实例，在 `apply_randomization: true` 时不一定是阻塞。每个池需要至少一个有效 USD 及相应抓取标注；`dexpick` 需要 `dexpick_pose.yaml`，普通 `pick` 通常需要 `Aligned_grasp_sparse.npy`。最小资产集合会改变可采样实例范围，因此结果只代表该受限资产集合。预检不保证所有 USD 嵌套纹理、外部引用或控制器资源齐全，实际加载结果单独记录。

已交付的三条配对视频使用固定资产实例、省略可选杂物并记录在 `task-provenance.json` 中；本审计保留原 YAML 的随机化逻辑，且只跑一个 seed。两者的配置实例和布局不同，不能用某次原配置规划失败否定已经验收的配对 episode，也不能用配对 episode 成功替代原配置的覆盖测试。

测试依次调用原配置的 `init_task → randomization → generate_seq`；流体配置使用官方要求的 `plan_with_render`。这是官方工作流 API 测试，不是完整 Nimbus 分布式 launcher 测试。每个配置独立进程、默认 seed 43，共享 GPU 文件锁，超时终止当前进程组。已有完成结果复用，重测使用 `--family basic/conveyor_beef_sandwich --tag extended-timeout --timeout 600`，保存到独立的 `retests/<tag>/`，保留基线。最初批次上限为 300 秒，发现传送带仍在推进后，后续上限延长到 600 秒；初始超时单独重测。

每次尝试保存：

- `result.json`：阶段、状态、seed、耗时、异常；新版 runner 另保存配置/runner SHA-256 和 engine commit。
- `stdout.log` / `kit.log`：初始化、规划和仿真日志。
- `resolved-task.json`：成功随机化后实际布局、资产实例和任务配置。
- 成功规划的 `official-plan.pkl`：官方 `dump_plan_info()`，包含配置、WorldRecorder 和 logger；`scene.usdc` 为场景层导出，仍需原资产引用。

`planning_succeeded` 只表示官方 API 返回非零帧数；`planning_failed` 是该 seed 未通过；`runtime_error`、`timeout`、依赖阻塞分别报告。源代码缺失、资产缺失、随机布局失败不能混为算法失败。少量随机种子不能证明一项任务不可实现。

### 本次审计的修复与复测

保留修改前的 `family-runtime-results.json`，以下复测分别写入 `retests/<tag>/`：

- `clean-serial-600`：两项传送带任务。旧超时处理只等待 shell 退出，可能遗留 Kit 子进程；现在会清理整个独立进程组，并用真实子进程回归测试验证。原基线的短暂并发及性能限制记录在 `execution-caveats.json`。
- `texture-pools`：三项擦拭任务。补齐约 2.9 MB 污渍颜色贴图后仍因缺少桌面纹理库报错，保留这次不完整的依赖补齐结果。
- `arena-textures`：再补齐约 5 MB 的官方深色/浅色桌面纹理库，重测三项擦拭。预检检查任务物体与场景 fixtures 的纹理池；不修改任务配置或规划算法。
- `source-fixes`：加热微波炉食物、倒水、失败恢复抓取、翻包裹。分别修正水平放置的参数读取分支、抓取后抬升的未定义夹爪命令、已有 robot 坐标分支被校验拒绝、公开配置 `ee_axis` 与技能参数名不一致。没有修改原 YAML 的动作目标；每次结果记录 engine commit 和配置 hash。

异常消失不等于规划成功，以复测结果为准。缺少第二台机器人声明的协作配置，以及静态关节物体缺少 `obj_info_path` 的配置单独标记为源码配置缺陷；不通过猜测场景或机器人声明伪装成官方原例。

倒水复测在修复 `Manualpick` 后继续触发了另一个上游缺口：左右臂配置都启用 `approach__rotate.dummy_forward`，而 `Approach_Rotate.get_tgt_js()` 直接抛出 `NotImplementedError`。此任务仍未跑通；依赖预检只检查技能是否注册，不能保证技能的每个配置分支都有实现。

`check_plans.py` 对成功结果核对 WorldRecorder 帧数、prim 数量、有限位姿与四元数归一化，并记录物体 logger 的字段和帧数。此检查不能证明接触正确、终态成功或原视频逐帧对应。官方 plan 的记录顺序不能直接代替经过校验的物理时间戳；用于 Human ego 的完整时间轴仍由 `work/task-pairs` 的显式记录器生成。

## 已发布机器人数据能否直接生成对应 Human ego

对 `sim_updated/articulation_tasks/franka/close_the_washingmachine_left.tar.gz` 只取最多 16 MiB 压缩前缀，读取其中真实 Parquet 的 Hugging Face schema 元数据。另外把 `sim_updated_lerobotv30` 同名样本的压缩前缀增至最多 32 MiB（复用已读前缀），读取其中 21,484,985 字节的实际 Parquet；v2.1 和 v3.0 样本均为同样的 29 个字段。这两个样本包含机器人关节、夹爪、TCP/末端位姿、相机参数和时间戳，**没有完整物体/连杆世界位姿、场景布局与资产实例**。五个官方 A1 LeRobot converter 的 FEATURES 也没有完整的物体状态字段。证据保存为 `actual-parquet-metadata.json`、`v30-actual-parquet-metadata.json` 和 `converter-schemas.json`。较早 `sim` 的 16 MiB 前缀只读到了视频文件，不能由此前缀推断整个归档的内容。

所以必须区分：

1. **重新生成配对数据**：从官方任务配置规划新的机器人 episode，同时记录完整场景状态；人体 IK 使用其物体接触轨迹，固定眼位重放。这条路线已验收挂杯、关闭微波炉、插花三项，参见 `work/task-pairs/README.md`。
2. **逐条对应已发布 HF episode**：需要与该 episode 匹配的原始 plan / WorldRecorder / 含物体状态的原始日志及场景。仅用上述 LeRobot schema 里的机器人状态，不能唯一确定物体是否滑动、被放置到何处，以及门的运动。重新运行同名任务不会恢复同一条发布轨迹。

这不是声称所有 HF 压缩包都没有额外原始数据；检查范围是实际抽样文件、公开目录及官方转换器。还没有找到足以严格重放所有已发布 episode 的逐条场景状态来源。

另用 PyArrow 17.0.0 直接读取了已抽取的 59 个 Parquet 文件：58 个来自上述 v2.1 压缩包前缀，1 个来自同任务 v3.0 压缩包前缀。所有真实列结构均为同一组 29 列，且与各文件的 Hugging Face 元数据一致；文件 hash、行数、归档成员路径与类型见 `physical-parquet-schemas.json`。这些仍是同一个关洗衣机门任务的两个版本样本，不代表检查过全部任务的每条数据。

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

另有一条直接的官方线索：[InternData-A1 discussion #11](https://huggingface.co/datasets/InternRobotics/InternData-A1/discussions/11) 中，Intern Robotics 成员回复应结合 InternDataEngine 与 SIM1 使用。[SIM1](https://github.com/InternRobotics/SIM1) 是基于 Newton/Warp 的双臂布料管线，包含生成、平滑、重放、过滤及可选渲染；它不在本仓库 Isaac Sim 4.1 的任务测试范围内。这说明布料任务需要另核对该上游管线，不能直接列作“官方完全未开源”。该回复也没有提供 A1 每条已发布 episode 到原始场景状态的映射。

源码名称、data.task_dir 和语言指令的检查尚未找到折衣/折毛巾、炉灶旋钮、扫垃圾、识价取物、选饮料、扫码等部分发布任务的完整对应配置。因此不能承诺公开仓库可完整复现论文全部 70 项。通用技能可能实现这些任务，需补任务配置与专门验收，不能当成现成例子。

来源：[官方数据集](https://huggingface.co/datasets/InternRobotics/InternData-A1)、[论文](https://arxiv.org/html/2511.16651v1)、[官方 quickstart（含流体模式要求）](https://internrobotics.github.io/InternDataEngine-Docs/guides/quickstart.html)、[安装说明](https://internrobotics.github.io/InternDataEngine-Docs/guides/installation.html)。
