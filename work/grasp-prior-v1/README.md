# GrabNet + ContactOpt + 人体姿态先验接入

当前状态：**准备阶段，尚未部署或跑通神经模型，也没有新版抓握视频。**
2026-11-17 新服务器 SSH 连接中断后连续超时，官方模型文件的现有库存未能查完。
本目录目前提供上游版本清单、模型预检、源代码拉取和配对不变量保护；不是已经完成的推理实现。

## 输入与不能改变的内容

只使用新机器已经成功的两条 episode：

- `run/task-pairs/hang_cup/seed-43-explicit`
- `run/task-pairs/insert_flower/seed-44-explicit`

基线为 camera-v3，代码提交 `32b821fc9f7373ac470a4af391132f2b7060b08f`。
源物体/连杆状态、时间戳、当前 ego 和正面相机的矩阵及焦距、采样帧都不能改变。
保持 Worker 原生外观、骨架和 Isaac Sim 4.1。候选姿态写入独立目录，不覆盖 `human/`。
人体根和原生眼位的祖先骨骼锁定，姿态先验用于肩臂选择；不能通过移动身体或相机降低抓握误差。

所有新增环境、上游源码、模型和输出都存放在：

```text
/mnt/data/pengjiaqi/egoengine-workspace/run/grasp-prior-v1/
  sources/       # 从官方仓库在新服务器直接拉取
  models/        # 合法下载的模型，或指向工作区中已有文件的链接
  env/           # 独立求解环境，不升级 Isaac 的 Python 包
  cache/
  logs/
  episodes/      # 基线小文件、抓握候选、验证和对比结果
```

## 模型获取与复用

`sources.json` 固定上游 commit 和必要文件。`preflight.py` 接受 JSON 路径映射，优先使用现有文件，不重复下载，不载入 pickle，也不把“文件存在”判定为推理成功。

- [MANO](https://mano.is.tue.mpg.de/)：官方账号下载 `MANO_RIGHT.pkl`。manopth 仅有代码，不包含模型。
- [GrabNet / GRAB](https://grab.is.tue.mpg.de/)：下载 CoarseNet、RefineNet 权重；此实验不需要完整 GRAB 训练集。
- [ContactOpt](https://github.com/facebookresearch/ContactOpt)：固定仓库中已经包含约 5.8 MB 的 DeepContact 权重。
- [SMPL-X / VPoser](https://smpl-x.is.tue.mpg.de/)：使用官方 SMPL-X 模型、VPoser 权重和配套网络配置。

权重下载需要各官方站点相应授权。不要提交账号密码、模型文件或带访问凭据的下载地址到 Git。
缺少文件时停止对应推理，不允许随机权重、几何启发式或旧结果冒充 GrabNet/ContactOpt 输出。

```bash
workspace=/mnt/data/pengjiaqi/egoengine-workspace
code="$workspace/egoengine/work/grasp-prior-v1"
run="$workspace/run/grasp-prior-v1"

# 只获取固定版本源码和仓库自带的小型模型，不获取训练数据集。
python3 "$code/fetch_sources.py" "$run"
python3 "$code/preflight.py" "$run" --report "$run/logs/preflight.json"
# 若文件已经在其他工作区子目录，使用 --model-paths 指向本地 JSON，键见 sources.json。
```

求解环境安装和模型前向运行尚待在新服务器验证；不能直接将旧项目的 requirements 装入 Isaac 环境。
固定的是原 VPoser 2.2.2.0 源码，避免当前 staging 对更新 Python/Torch 的强制要求；这不等于已经验证运行兼容性。

## 冻结与验收

恢复连接后先冻结两条基线。脚本只复制小型轨迹、报告和视频，不复制资产、USD 场景或渲染帧缓存；目标目录存在时拒绝覆盖。

```bash
episode="$workspace/run/task-pairs/hang_cup/seed-43-explicit"
bash "$workspace/run/human41/usd_python.sh" "$code/baseline.py" freeze \
  "$episode" "$run/episodes/hang_cup/before"

# 候选动画与渲染生成后执行：
bash "$workspace/run/human41/usd_python.sh" "$code/baseline.py" check \
  "$run/episodes/hang_cup/before" "$run/episodes/hang_cup/after" \
  --render-report "$run/episodes/hang_cup/after/render/verification.json"
```

本机已经用真实的 camera-v3 轨迹包验证保护逻辑：原样输入通过；修改物体、时间、相机或头部绑定各自都会失败；肩臂改动允许进入后续质量检查。这只验证配对约束，没有验证神经网络或新版动作。

```bash
python verify_baseline.py /path/to/paired-trajectories.zip /path/to/test-output
```

## 后续实施边界

1. 从源 USD 导出真实米制物体网格及抓取事件，不使用 GrabNet 示例的自动缩小大物体逻辑。
2. 批量生成抓握候选；挂杯优先杯身侧握、给杯架留出区域，花茎采用对捏，整束花另按束径选择环握。
3. 调用 DeepContact 和 ContactOpt，明确 `w_obj_rot=0`，保留原物体状态；保留调用的模型散列和优化记录。
4. 将 MANO 指节/表面目标映射到 Worker，结合姿态先验求肩臂姿态，并在 Worker 实际网格上复验接触。当前杯子和花的原人体都用左手，右手网络需要显式镜像几何与坐标约定，不复制右手局部角度到左手。
5. 检查指腹接触、穿透、滑移、腕部及关节连续性。先看接近/闭合/释放近景，再渲染完整三视角，与冻结的基线按同一源帧拼接。

在这些步骤实际运行并通过之前，不产生“已优化”的验收结论。
