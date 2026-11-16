# 从官方任务重新生成 Robot–Human 配对数据

此目录在保留 InternDataEngine 源码的基础上，调用官方 `plan_with_render`、cuRobo 和 kPAM 技能规划。新增代码负责完整状态记录、任务验证、Worker 人体接触 IK、几何重放与三视角编码。不会把失败轨迹标成成功，也不会通过移动物体来修复机器人任务。

## 任务候选

以下配置路径均相对于 `workflows/simbox/core/configs/tasks/`，已检查文件存在。**配置存在不等于该任务已在新机器跑通**；执行通过状态由每条 episode 的 `result.json` 和 `source-validation.json` 给出。

| 任务 | 类型 | 配置 | 转换要求 |
|---|---|---|---|
| 杯子放上杯架 | 单手抓取与放置 | `basic/split_aloha/hang_the_cup_on_rack/hang_the_cup_on_rack_part0.yaml` | 杯子局部接触锁，释放后撤手 |
| 香蕉双手交接后放盘 | 双手交接 | `long_horizon/split_aloha/handover/lr/dish.yaml` | 两手分别建立接触锁，交接重叠区间 |
| 关闭微波炉 | 关节物体操作 | `art/split_aloha/close_the_microwave/left/close_the_microwave_part0.yaml` | 保存门关节及连杆，手跟随门的接触区域 |
| 插花入瓶 | 刚体插入 | `basic/split_aloha/insert_the_flower_in_vase/insert_the_flower_in_vase_part0.yaml` | 细长物体握持与插入接触 |
| 插笔入笔筒 | 刚体插入 | `basic/split_aloha/insert_the_markpen_in_penholder/insert_the_markpen_in_penholder_part0.yaml` | 精细手指抓握适配 |
| 叠两只碗 | 刚体堆叠 | `basic/split_aloha/stack_bowls/stack_two_l.yaml` | 碗缘抓握，放开后稳定检查 |
| 叠块后双手抬盘 | 双手搬运 | `basic/split_aloha/stack_cubes_lift/lr.yaml` | 已有独立稳定放置修复和 Worker 回归流程 |
| 打开微波炉 | 关节物体操作 | `art/split_aloha/open_the_microwave/left/open_the_microwave_part0.yaml` | 把手握持与门轴轨迹 |
| 抓起香蕉 | 单手拿起 | `pick_and_place/split_aloha/single_pick/left/omniobject3d-banana.yaml` | 物体局部接触锁 |

首批选择挂杯、关闭微波炉和插花。双手交接的新机器三个 seed 未通过规划，失败记录保留，不生成伪成功样本；其他项目是下一批候选。折布、液体倾倒、擦除污渍暂不纳入仅刚体位姿的通用转换，需要额外记录网格、粒子或材质变化。

## 运行

前提是仓库根 README 的 Isaac Sim 4.1、cuRobo、基础场景、Worker 和动作参考库安装完成。所有环境、资产和输出均留在一个工作区。

```bash
workspace=/mnt/data/pengjiaqi/egoengine-workspace
root="$workspace/run"
repo="$workspace/egoengine"
mkdir -p "$root/task-pairs"
cp "$repo"/work/task-pairs/*.py "$repo"/work/task-pairs/catalog.json "$root/task-pairs/"
cp "$repo"/work/human-natural-v4/{bake,ego_mask}.py "$root/task-pairs/"

# 先列清单。仅缺失或校验不符的文件会在 --download 时下载。
bash "$root/human41/usd_python.sh" "$root/task-pairs/assets.py" "$root" \
  --endpoint https://hf-mirror.com --token-file "$workspace/config/hf_token"
# 仅在用户授权使用该镜像后，将上面命令加 --download。

bash "$root/human41/usd_python.sh" "$root/task-pairs/batch.py" "$workspace" --seeds 43 44 42 --tag explicit
```

`batch.py` 顺序运行 GPU 任务，保留各个 seed 的失败记录，不覆盖成功样本。首批资产只下载任务需要的 USD、材质、纹理和规划元数据，不下载数据集 episode 压缩包。`asset-manifest.json` 保存大小和 SHA-256。受限数据必须使用已获授权账号，API 元数据也需要认证，否则 Hugging Face 会隐藏 LFS 哈希。

选取 `selected.json` 中某条 episode 后：

```bash
episode="$root/task-pairs/hang_cup/seed-43-explicit"  # 替换成实际通过的路径
bash "$root/human41/usd_python.sh" "$root/task-pairs/validate.py" "$episode"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
case "$episode" in
  */insert_flower/*)
    bash "$root/human41/usd_python.sh" "$root/task-pairs/human.py" "$root" "$episode" --grasp-roll -20
    bash "$root/human41/usd_python.sh" "$root/task-pairs/refine_fingers.py" "$root" "$episode"
    bash "$root/human41/usd_python.sh" "$root/task-pairs/gaze.py" "$root" "$episode" --pitch-deg 26 --focal-mm 7
    ;;
  *)
    bash "$root/human41/usd_python.sh" "$root/task-pairs/human.py" "$root" "$episode"
    bash "$root/human41/usd_python.sh" "$root/task-pairs/gaze.py" "$root" "$episode"
    ;;
esac
# 插花的额外参数调整人体握持方向、指尖和固定相机视野，不改变物体运动。
bash "$root/human41/usd_python.sh" "$root/task-pairs/check_human.py" "$episode"
bash "$root/human41/usd_python.sh" "$root/task-pairs/bake.py" --root "$root" --folder "$episode/human" --stride 3
bash "$root/human41/usd_python.sh" "$root/task-pairs/ego_mask.py" --root "$root" --folder "$episode/human"
bash "$root/run_env41.sh" "$root/task-pairs/render.py" "$episode" --preview
# 先看 preview 的抓取、释放和末帧，再跑全程。
bash "$root/run_env41.sh" "$root/task-pairs/render.py" "$episode"
bash "$root/human41/usd_python.sh" "$root/task-pairs/check_cameras.py" "$episode"
bash "$root/human41/usd_python.sh" "$root/task-pairs/encode.py" "$episode"
```

## 文件与对应关系

- `task-provenance.json`：官方配置、seed 和所有配置调整。技能序列不变；固定资产实例，省略可选杂物，降低分辨率。
- `source/scene.usdc`：原机器人场景；保留对本工作区资产的引用。
- `source/world-tracks.npz`：完整原始时间戳、物理步号、所有已登记 prim 的世界矩阵（含缩放）、物体根位姿、活动关节、机器人关节、TCP、相机、夹爪宽度。
- `source/events.json`：技能、控制命令与对应帧。
- `source/robot-raw.mp4`：逐次状态采样对应的机器人相机，校验帧数和物理时间。
- `source-validation.json`：官方成功、抬升/关闭、释放/交接、终态稳定、时间连续性与视频帧数检查。
- `human/human-animation.npz`：原生 Worker 骨架、独立人体 IK，复制原物体状态与时间；`retarget-report.json` 保存误差和接触区间。
- `human/skin-cache/`：原模型网格蒙皮、UV 与材质，三帧采样一次用于低成本预览；原始轨迹仍保存每一帧。
- `human/render/delivery/`：完整时长 ego 和机器人/ego/正面拼接视频及编码校验。

ego 相机固定在人体双眼之间，朝向桌子法线，消除横滚；没有逐帧手部、物体或 TCP 跟踪。头部采用固定姿态。正面相机固定在桌子前方、沿桌子法线取景，桌沿保持水平。插花使用固定 26° 俯角与 7 mm 广角，其他两项使用固定 35° 俯角与 10 mm 焦距；这些参数在整条视频中不变。`check_cameras.py` 独立检查眼位绑定、相机稳定、桌沿方向及原物体状态。

三视角使用同一个源帧索引和时间。原始状态为 30 Hz，调试画面约 5 Hz，并额外保留接触关键帧；编码仍为 30 fps，保持原时长。两个采样时刻之间保持同一幅图，不插值篡改物体轨迹。首尾都包含。渲染先做“末帧→明显不同的姿态→末帧”检查，用重复帧误差排查 Isaac 4.1 动态网格滞后。首次充分预热，审计帧多次取样平均，减少 RTX 光照噪声，误差阈值保持不变。

人体视图把站立地面降低到原生模型脚底，并在原桌子下面加承台，允许人物直立操作较高的工作台；桌子和任务物体的轨迹不变。这一布景差异记在渲染报告中。正面观察相机位于室内，桌子仍会产生正常遮挡。

这是**机器人生成物体运动 + 人体几何重放**。人体有独立骨架/IK，但未进行人体驱动物体的动力学求解；指尖贴合误差、手腕误差与视觉检查决定能否作为训练数据，不能把初步渲染当成人类自然动作的验证。

本次源任务验收：挂杯 `seed-43-explicit`，472 帧 / 15.73 秒；关闭微波炉 `seed-44-explicit`，554 帧 / 18.47 秒；插花 `seed-44-explicit`，593 帧 / 19.77 秒。以各 episode 的完整验收文件为准。运行 `package.py "$root"` 可打包轨迹、人体姿态与校验报告，自动排除大资产、场景 USD 和帧缓存；这些文件保留在服务器原目录。

## 兼容修复

- 当前 Drake 使用 `discrete_contact_approximation="sap"` 和 `Parser.AddModels`；兼容分支保留旧版 API 与原 SAP 意图。参见 [Drake 官方说明](https://drake.mit.edu/doxygen_cxx/structdrake_1_1multibody_1_1_multibody_plant_config.html)。
- Kit 的 app 更新可能在一次控制循环中推进多个物理步。本记录器通过 `World.step(step_sim=False)` 执行原任务的 pre_step，显式调用一次 PhysX `simulate(dt)`，并在暂停 timeline 后渲染。以实际模拟调用和官方 dt 建立时间轴，另外保留 `isaac_callback_time_s`、`isaac_callback_step` 供审计；断言渲染不推进物理。导入 USD 的额外空 PhysicsScene 可导致回调重复计数，因此不把回调次数当作模拟调用次数。
