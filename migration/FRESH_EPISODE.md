# 全新部署与新任务配对

此路径在新机器重新运行双臂叠块、抬托盘任务，再将**本次同一 episode** 转为人物视频。
不复制原服务器的环境、模型、轨迹或人物动画。它复现同一种任务和呈现方式，
不承诺与历史 1507 帧逐位相同。新机器已完成 1490 帧机械臂任务及完整时长的
Worker 三视角调试视频验证；调试配置为 640×360、源帧采样步长 3。

## 一个目录容纳代码、环境、数据和输出

```bash
export WORKSPACE=/mnt/data/pengjiaqi/egoengine-workspace
mkdir -p "$WORKSPACE"/{config,logs,tmp}
# 已 clone 时检查 remote/status，不重复 clone 或覆盖修改。
git clone https://github.com/steinate/egoengine.git "$WORKSPACE/egoengine"
export EGO_ROOT="$WORKSPACE/egoengine"
export PAIR_ROOT="$WORKSPACE/run"
cd "$EGO_ROOT"
python3 migration/prepare_workspace.py "$PAIR_ROOT"
export TMPDIR="$PAIR_ROOT/tmp"
export PIP_CACHE_DIR="$PAIR_ROOT/cache41/pip"
export PYTHONPYCACHEPREFIX="$PAIR_ROOT/cache41/pycache"
```

代码在 `egoengine/`，其余项目内容在 `run/`。先检查本机已有文件和校验信息，
只下载缺失文件，不下载旧复现包。

## 环境与任务资产

可执行 `bash migration/bootstrap_runtime.sh "$PAIR_ROOT"` 下载并解压固定散列的 NVIDIA 官方 Isaac Sim 4.1，
或使用 [环境文档](README.md#isaac-sim-410) 中的手动命令；随后
安装 CUDA 11.8 和 Python 依赖。若 GCC/ffmpeg 等也要收在运行目录，Ubuntu 24.04 可执行：

```bash
bash migration/bootstrap_system.sh "$PAIR_ROOT"
python3 "$PAIR_ROOT/install_cuda118.py"
export CUDA_HOME="$PAIR_ROOT/env/cuda-11.8"
export CC="$PAIR_ROOT/env/gcc11/usr/bin/gcc-11"
export CXX="$PAIR_ROOT/env/gcc11/usr/bin/g++-11"
cat > "$PAIR_ROOT/toolchain.env" <<EOF_TOOLCHAIN
export CUDA_HOME="$CUDA_HOME"
export CC="$CC"
export CXX="$CXX"
export MAX_JOBS=4
EOF_TOOLCHAIN

# SDK 自带的 Python 3.10；额外包安装在项目目录，不覆盖 SDK 的包。
export PYTHONPATH="$PAIR_ROOT/env/python310"
bash "$PAIR_ROOT/runtime41/python.sh" -m pip install \
  --target "$PAIR_ROOT/env/python310" --upgrade pip==26.1.2
bash "$PAIR_ROOT/runtime41/python.sh" -m pip install \
  --target "$PAIR_ROOT/env/python310" --upgrade --no-compile \
  -r "$EGO_ROOT/work/isaac41/requirements-extra-linux310.lock.txt"
```

脚本只下载和解包 apt 包到 `run/env/system/`，不替换系统驱动。
仍依赖宿主 Ubuntu 基础系统和 NVIDIA 驱动，并非独立操作系统镜像。

本次 Linux/Python 3.10 的 131 个额外依赖版本保存在
`work/isaac41/requirements-extra-linux310.lock.txt`。环境文档中的 pip 安装命令可用此文件
替代基础 requirements，以固定传递依赖版本；SDK 自带 Torch/USD/Warp 仍由固定 SDK 提供。

GPU 容器还需检查 `/usr/share/nvidia/nvoptix.bin`。这是
[NVIDIA 驱动的 OptiX 数据文件](https://download.nvidia.com/XFree86/Linux-x86_64/570.124.04/README/installedcomponents.html)，
缺失时 PathTracing 降噪会失败，即使 CUDA 和规划器检查正常也可能出现严重噪点。
已有文件时复用；当前 570.124.04 容器缺失时可执行：

```bash
bash migration/bootstrap_optix.sh "$PAIR_ROOT" --system-link
```

脚本校验匹配版本的 NVIDIA 包，仅提取降噪数据，不运行驱动安装器。
数据保存在 `run/env/nvidia-570.124.04/`；唯一的系统路径新增项是
`/usr/share/nvidia/nvoptix.bin` 指向该文件的符号链接，不覆盖已有文件。
不允许创建系统链接时，可不传 `--system-link`，由容器启动配置将该文件只读挂载到同一位置。
其他驱动版本需使用匹配版本的文件，不能直接混用本包。

InternData-A1 是受限数据集：先在 Hugging Face 同意仓库条款，再将读取 token
写入 `$WORKSPACE/config/hf_token`，权限 600；不要放入代码或命令行参数。

```bash
python3 migration/task_assets.py --root "$PAIR_ROOT" --download \
  --token-file "$WORKSPACE/config/hf_token" --workers 8
python3 migration/task_assets.py --root "$PAIR_ROOT" --verify
```

主站不可访问时，只有在你同意把 token 交给该镜像后，才加入
`--endpoint https://hf-mirror.com`。默认不会使用第三方镜像。
下载器复用已校验文件、续传中断文件，并逐个核对上游散列。

资产校验通过后，在目标 GPU 编译本仓库保留的 CuRobo 源码：

```bash
source "$PAIR_ROOT/toolchain.env"
mkdir -p "$PAIR_ROOT/build/curobo"
cp -a "$EGO_ROOT/deps/curobo/." "$PAIR_ROOT/build/curobo/"
cp -a "$PAIR_ROOT/assets/InternDataAssets/curobo/src/curobo/content/." \
  "$PAIR_ROOT/build/curobo/src/curobo/content/"
bash migration/run_engine.sh "$PAIR_ROOT" -m pip install \
  --no-deps --no-build-isolation --target "$PAIR_ROOT/env/curobo41-built" "$PAIR_ROOT/build/curobo"
bash migration/run_engine.sh "$PAIR_ROOT" "$EGO_ROOT/migration/check_environment.py" \
  > "$WORKSPACE/logs/environment-check.log" 2>&1
grep -F ENVIRONMENT_OK "$WORKSPACE/logs/environment-check.log"
```

必须看到 `ENVIRONMENT_OK`，不能仅凭安装目录存在判断成功。重建时使用新的构建/安装目录，
不混用其他 GPU 或 Torch ABI 的二进制；更多说明见 [构建文档](README.md#编译-curobo-并检查环境)。

## 完整机器人任务

```bash
bash migration/run_engine.sh "$PAIR_ROOT" "$PAIR_ROOT/robot-stack-v2/configure.py"
bash migration/run_engine.sh "$PAIR_ROOT" -m unittest human_pair.test_geometry
export TRIAL="$PAIR_ROOT/robot-stack-v2/new-machine-trial01"
set -o pipefail
bash migration/run_engine.sh "$PAIR_ROOT" "$PAIR_ROOT/robot-stack-v2/run.py" \
  --trial new-machine-trial01 --seed 42 2>&1 | tee "$WORKSPACE/logs/robot-trial01.log"
bash "$PAIR_ROOT/human41/usd_python.sh" "$PAIR_ROOT/robot-stack-v2/validate_stack.py" "$TRIAL"
```

使用仓库根目录的 InternDataEngine、官方规划/渲染/记录工作流与本项目 `stable_place` 修复。
物体运动来自物理仿真，不能用手写位姿轨迹替代任务成功。
必须检查 `stack-validation.json` 的 `passed`；保留失败 trial，重跑使用新名称。

找到本次官方输出中包含 `lmdb/` 的时间戳目录，选择与该 trial 对应的 episode：

```bash
export EPISODE="$PAIR_ROOT/robot-stack-v2/official-output/BananaBaseTask/split_aloha/stack_lift_cubes/stack_verified_v2/本次时间戳"
bash "$PAIR_ROOT/run_env41.sh" "$EGO_ROOT/human_pair/export_dual_grasp.py" \
  "$EPISODE" "$TRIAL/export" "$PAIR_ROOT/robot-stack-v2/task.yaml"
bash "$PAIR_ROOT/human41/usd_python.sh" "$PAIR_ROOT/robot-stack-v2/export_episode.py" \
  --trial "$TRIAL" --robot-export "$TRIAL/export"
```

导出器核对官方记录与诊断轨迹的帧数、位置，生成世界位姿、场景、机器人视频和事件接触时间。
已有 `source/world-tracks.npz` 时拒绝覆盖。源记录步索引与 15 fps 视频时间分别保存。

## 原始 Worker 真人风格人物（本次目标）

Worker 是最初非动漫版本使用的 Reallusion 原生角色，保留其身体、手、UV 和贴图。
无需 Blender、安柏、扫描手或历史人物动画。公共样例的使用范围以随包许可为准。

```bash
python3 migration/bootstrap_worker.py "$PAIR_ROOT"
bash migration/run_worker_motion.sh "$PAIR_ROOT" > "$WORKSPACE/logs/worker-motion.log" 2>&1
```

下载器只读取 NVIDIA ZIP 中 Worker 和许可文件的 HTTP 范围，不下载整份人物包；
已有文件按 ZIP CRC/长度复核复用，并输出 SHA256 清单。
`run_worker_motion.sh` 读取当前 `human-stack-v3/source/` 的完整轨迹与事件，
从原生骨架和随包动作库初始化。固定直立躯干，通过人体整体站位与支撑高度匹配桌面，
按人体骨长优化双臂、手指和时间平滑，随后验证源轨迹逐位一致、接触漂移与相机覆盖。
遇到验收失败会停止，不能把失败输出当作已完成视频。

在 `WORKER_MOTION_AND_SKIN_READY` 后，按实际事件选择关键帧预览：

```bash
bash "$PAIR_ROOT/run_env41.sh" "$PAIR_ROOT/human-natural-v4/render.py" \
  --frames 0,135,429,746,1023,1314,1489 --preview --view both --job preview
# 上面的帧号仅适用于本次 1490 帧任务；其他 episode 从 contact-schedule.json 读取。
# 调试优先：单进程、640×360 实时 RTX，先做末帧/首帧/末帧同步检查。
# 每 3 个源帧采样一次，三路同步保持到下一个采样时刻；覆盖完整任务时长，
# 明确标记 sampled debug，不能当成逐帧 15 fps 渲染。
bash "$PAIR_ROOT/human-natural-v4/render_debug.sh"
# 需要检查快速动作时改为逐帧：EGO_DEBUG_STRIDE=1 bash .../render_debug.sh
# 视觉检查通过后，需要完整逐帧版本再运行（默认仍为低分辨率实时渲染）：
bash "$PAIR_ROOT/human-natural-v4/render_full.sh"
# 明确需要高质量输出时才开启 PathTracing：
# EGO_RENDER_QUALITY=final bash "$PAIR_ROOT/human-natural-v4/render_full.sh"
```

调试输出在 `run/human-natural-v4/debug-<时间戳>-<进程号>/delivery/`：
`human-ego-debug.mp4`、`robot-ego-front-debug.mp4`、`debug-verification.json`。
验证文件记录实际渲染器、源帧号、时间戳、动画与物体轨迹哈希、重复末帧画面差异及耗时。
同步检查失败则停止，不继续整段渲染。每个调试运行使用独立目录，避免混入旧图片。
默认只运行一个 GPU 进程；完整渲染的并发上限为 2，避免多份 Isaac 启动争抢 CPU。

完整逐帧输出在 `run/human-natural-v4/delivery/`：`human-ego-full.mp4`、
`human-front-full.mp4`、`robot-ego-front-full.mp4` 与 `paired-world-trajectories.npz`。
本次新任务的证据见 `provenance/worker-debug-validation.json`：当前 Worker 原生模型、
当前机器人轨迹、完整任务时长。逐帧视频需要将调试步长设为 1 或执行 `render_full.sh`。

## 可选：安柏原版角色与原生骨架 IK

```bash
bash migration/bootstrap_character.sh "$PAIR_ROOT"
export OPENBLAS_NUM_THREADS=1
bash "$PAIR_ROOT/human41/usd_python.sh" "$PAIR_ROOT/anime-human-v1/solve_motion.py" --native-contacts
bash "$PAIR_ROOT/human41/usd_python.sh" "$PAIR_ROOT/anime-human-v1/verify.py"
bash "$PAIR_ROOT/human41/usd_python.sh" "$PAIR_ROOT/anime-human-v1/bake_and_template.py"
```

角色是仓库当前支持的安柏 2.0，保留原网格、骨架、UV、贴图和蒙皮权重；
使用条款见 [ASSETS.md](../ASSETS.md)。
接触解算直接拟合方块表面与托盘边缘，不需要历史人物动画，也不复制机器人关节角。
保持骨盆与脊柱直立、固定人体臂长、肘部朝外；保留物体源位姿和时间轴。
ego 相机保留原生眼部位置，根据完整轨迹拟合固定俯仰角，确保抓取物体全程入镜。
这属于几何配对的视觉重放，不等于重新验证人体接触动力学。

## 可选安柏的关键帧检查与完整视频

从 `source/contact-schedule.json` 读取实际抓取、释放、抬盘帧，替换下面的占位帧号：

```bash
bash "$PAIR_ROOT/run_env41.sh" "$PAIR_ROOT/anime-human-v1/render.py" \
  --frames 0,抓取帧,抬盘帧 --preview --view both --job preview
```

检查 ego/front 的贴图、站姿、接触、完整场景和物体误差。解决错误后再渲染全片：

```bash
N=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["frames"])' \
  "$PAIR_ROOT/anime-human-v1/source/scene-meta.json")
for view in ego front; do
  bash "$PAIR_ROOT/run_env41.sh" "$PAIR_ROOT/anime-human-v1/render.py" \
    --view "$view" --start 0 --end "$N" --job full \
    > "$WORKSPACE/logs/render-$view.log" 2>&1
done
bash "$PAIR_ROOT/human41/usd_python.sh" "$PAIR_ROOT/anime-human-v1/encode.py"
```

验收标志为 `FULL_PAIR_COMPLETE`。结果在 `run/anime-human-v1/delivery/`：
完整 ego、正面、机器人/ego/正面同步视频，以及 `paired-world-trajectories.npz`、
`video-verification.json` 和校验清单。编码器核对所有源帧、轨迹、动画/代码散列与视频帧数。

