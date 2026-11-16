# 新机器环境安装与可选角色导入

完整顺序和验收标准以 [根 README](../README.md) 为入口。
这里展开环境安装与原生 PMX 导入。所有下载命令均为需要时手动执行，文档检查不会运行它们。
服务器现有环境、原始资产和旧快照无需变动。

## 环境安装

以下命令假定已 clone、设置 `EGO_ROOT`/`PAIR_ROOT`，并执行
`python3 migration/prepare_workspace.py "$PAIR_ROOT"`。
新机器使用独立运行目录；不要将 `PAIR_ROOT` 指向 VLA-Infra 原目录。
退出已有 Conda/其他 Python 虚拟环境，以免污染 Kit 解释器。

### 系统依赖

下面是 Ubuntu 的系统包安装示例，需要管理员权限；容器中由管理员安装对应包。
NVIDIA 驱动安装因机器而异，应先由 `nvidia-smi` 确认 GPU 可用。

```bash
sudo apt-get update
sudo apt-get install -y git unzip rsync ffmpeg build-essential gcc-11 g++-11 \
  pkg-config libglib2.0-0 libgl1 libx11-6 libxext6 libsm6 libxi6 libxrender1 \
  libxrandr2 libvulkan1 vulkan-tools fonts-dejavu-core
nvidia-smi
ffmpeg -version
```

实测环境为 Ubuntu 24.04.2 / NVIDIA L20 / 535.154.05，详细记录见
[原运行环境审计](../provenance/migration-runtime-audit.json)。
本文不把安装过程验证范围扩展到未实际测试的 GPU、系统或容器镜像。

### Isaac Sim 4.1.0

[上游安装说明](https://internrobotics.github.io/InternDataEngine-Docs/guides/installation.html)
推荐 4.1.0，并允许使用 SDK 自带 Python。当前项目固定复现 4.1.0。
官方最新下载入口见 [ASSETS.md](../ASSETS.md)，旧版公开直链未确认。
在有权访问 VLA-Infra 时，可以按需取得已有安装包：

```text
root@172.31.21.245:2222
/vepfs/public/pengjiaqi/interndata-human-pair/downloads/isaac-sim-4.1.0.zip
```

不自动传输该大文件。取得安装包后先查看 ZIP 的顶层结构，再解压；最终必须满足：

```bash
# 若包内直接包含 python.sh/kit/exts，解压命令如下：
mkdir -p "$PAIR_ROOT/runtime41"
unzip /path/to/isaac-sim-4.1.0.zip -d "$PAIR_ROOT/runtime41"
test -f "$PAIR_ROOT/runtime41/python.sh"
test -x "$PAIR_ROOT/runtime41/kit/python/bin/python3"
cat "$PAIR_ROOT/runtime41/VERSION"
bash "$PAIR_ROOT/runtime41/python.sh" -V
```

应为 Isaac Sim 4.1.0 和 Python 3.10；若 ZIP 多套一层目录，要调整到上面的层级。
**不要运行 `pip install isaacsim` 获取当前最新版，也不要给 Kit 安装另一个 `usd-core`。**

### CUDA 11.8 与 GCC 11

这里需要 `nvcc` 编译器，不只是 `nvidia-smi` 中显示的驱动 CUDA 兼容版本。
如果目标机器已有 CUDA 11.8，直接指定其目录，不重复下载。
若没有，可显式运行准备脚本生成的下载器：

```bash
# 可选，确实缺少 CUDA 11.8 时才执行。此命令会下载三个构建组件。
# 使用 Ubuntu 24.04 的系统 Python 3.12（tarfile 安全解包接口）。
python3 "$PAIR_ROOT/install_cuda118.py"
```

该脚本读取 NVIDIA 的 11.8.0 分发 JSON，只获取 `cuda_nvcc`、`cuda_cudart`、`cuda_cccl`，
校验 SHA256 后合并到 `$PAIR_ROOT/env/cuda-11.8`，不安装/替换显卡驱动。
不需要使用历史的 `setup_gcc11.sh`：它是原机器特殊 apt 目录的绕行方案。

```bash
# 如已有 /usr/local/cuda-11.8，改用该路径。
export CUDA_HOME="$PAIR_ROOT/env/cuda-11.8"
export CC=/usr/bin/gcc-11
export CXX=/usr/bin/g++-11
export MAX_JOBS=4
"$CUDA_HOME/bin/nvcc" --version
"$CXX" --version

# 保存；之后运行引擎前 source 此文件。
cat > "$PAIR_ROOT/toolchain.env" <<EOF_TOOLCHAIN
export CUDA_HOME="$CUDA_HOME"
export CC="$CC"
export CXX="$CXX"
export MAX_JOBS=4
EOF_TOOLCHAIN
source "$PAIR_ROOT/toolchain.env"
```

`run_engine.sh` 会尊重这些变量。`TORCH_CUDA_ARCH_LIST` 默认不设置，让 Torch 在编译时检测目标 GPU；
L20 实测值为 `8.9`。如果构建节点没有可见 GPU，需要按目标 GPU 显式设置正确架构，
不要照搬 L20 数值。更换架构时重新构建，不能只修改环境变量后继续使用旧扩展。

### 额外 Python 依赖

```bash
export PYTHONPATH="$PAIR_ROOT/env/python310"
export PIP_CACHE_DIR="$PAIR_ROOT/cache41/pip"
export TMPDIR="$PAIR_ROOT/tmp"
bash "$PAIR_ROOT/runtime41/python.sh" -m pip install \
  --target "$PAIR_ROOT/env/python310" --upgrade pip==26.1.2
bash "$PAIR_ROOT/runtime41/python.sh" -m pip install \
  --target "$PAIR_ROOT/env/python310" --upgrade \
  -r "$EGO_ROOT/work/isaac41/requirements-engine41.txt"

# 查看实际导入来源；不要另装最新 Torch 来“修复”版本差异。
bash "$PAIR_ROOT/runtime41/python.sh" -c \
  'import sys,numpy,torch; print(sys.version); print(numpy.__version__,numpy.__file__); print(torch.__version__,torch.version.cuda,torch.__file__)'
```

此处安装 NumPy 1.26.4，预期 Torch 2.2.2+cu118。Kit 启动后可能优先加载它自带的
NumPy 1.26.0：本次环境检查在独立恢复副本实际观察到该行为，检查会记录实际版本和路径，
接受 1.26.0/1.26.4，不接受 NumPy 2.x。不要为了统一显示版本而删除 Kit 自带包。
基础依赖显式固定了版本，但此 requirements
不是所有传递依赖的带散列 lockfile；安装后保留实际版本，环境检查不过不能继续宣称复现成功。
`usd-core`/Torch/Warp 由 Kit 提供，不对它们执行升级安装。

## 编译 CuRobo 并检查环境

先完成根 README 的资产步骤，确保 `InternDataAssets` 的三个子目录均存在。
规划器必须从仓库保存的源码编译；上游新版本的 API 不一定与该工作流兼容。
源码没有包含大网格，因此将所选资产中的 `content/` 补入**运行目录内的构建副本**。

```bash
source "$PAIR_ROOT/toolchain.env"
mkdir -p "$PAIR_ROOT/build/curobo"
cp -a "$EGO_ROOT/deps/curobo/." "$PAIR_ROOT/build/curobo/"
cp -a "$PAIR_ROOT/assets/InternDataAssets/curobo/src/curobo/content/." \
  "$PAIR_ROOT/build/curobo/src/curobo/content/"

# --no-deps 保留 Kit 的 Torch/Warp；--no-build-isolation 使用同一个 Torch ABI。
bash "$EGO_ROOT/migration/run_engine.sh" "$PAIR_ROOT" -m pip install \
  --no-deps --no-build-isolation --target "$PAIR_ROOT/env/curobo41-built" \
  "$PAIR_ROOT/build/curobo"

bash "$EGO_ROOT/migration/run_engine.sh" "$PAIR_ROOT" \
  "$EGO_ROOT/migration/check_environment.py" \
  > "$PAIR_ROOT/logs41/environment-check.log" 2>&1
grep -F ENVIRONMENT_OK "$PAIR_ROOT/logs41/environment-check.log"
```

必须出现 `ENVIRONMENT_OK`，它确认 Python/Torch/NumPy、GPU 操作及规划器扩展加载。
此检查先启动 Kit 再导入 MotionGen，避免错误地把尚未注册的 Warp 扩展判断为缺失。
真正的规划和任务成功仍由根 README 第 4 步验证。
若重建 CuRobo，先把旧 `env/curobo41-built/` 移至备份位置，在空目录重新安装；
不要将不同 ABI 的 `.so` 混在同一 target 中。

```bash
bash "$EGO_ROOT/migration/run_engine.sh" "$PAIR_ROOT" -m pip freeze \
  > "$PAIR_ROOT/logs41/environment-freeze.txt"
```

之后回到根 README，运行 `configure.py`、`run.py` 和 `validate_stack.py`。
新生成的机器人 episode 保留在独立 trial，不能直接覆盖原配对输入。

## 可选：原生角色导入

最稳妥的原视频复现路径是根 README 的 21 个输入文件，复用原生导出后重新解 IK、烘焙和渲染。
以下是**替代其中原生导出文件**的方式；原场景/轨迹/接触参考仍不可省略。

1. 从 [安柏原始 ZIP](https://activity.hdslb.com/blackboard/static/20210316/4d40bc4f98f94fbc71c235832ce3efd4/ApoSncaZI8.zip)
   按需取得 PMX，SHA256 为
   `4dafd2bc1251d7c90cc68e62fd3edda29aa137ae430dc382df19d44859ce52f5`。
   解压到 `$PAIR_ROOT/anime-human-v1/assets/amber/`，保留贴图相对路径。
   模型禁止商用和二次分发；代码仓库不发布模型本体。
2. 按 [Blender 链接与版本](../ASSETS.md) 准备 Blender 5.2.2。
   `deps/blender_mmd_tools/` 是保留的 4.5.14 导入器，要求 Blender ≥4.2，不能用 4.0.2。
   原导出在 macOS 5.2.2 完成，Linux 同版原始导入尚未作为迁移验收项目完整跑过。
3. 安装导入器需要的纯 Python OpenCC，再在 Blender 自带 Python 环境内执行脚本。

```bash
# 只安装小型导入依赖；不让系统 Python 执行依赖 bpy 的脚本。
python3 -m pip install --target "$PAIR_ROOT/anime-human-v1/tools/python-deps" \
  opencc-python-reimplemented==0.1.7
export BLENDER=/path/to/blender-5.2.2-linux-x64/blender
"$BLENDER" --background --factory-startup --python-exit-code 1 \
  --python "$PAIR_ROOT/anime-human-v1/import_amber.py"
"$BLENDER" --background --factory-startup --python-exit-code 1 \
  --python "$PAIR_ROOT/anime-human-v1/export_native.py"
```

预期输出 `amber-native.blend`、`amber-rig.npz`、`amber-mesh.npz`、
`materials.json`、`textures/`、`asset-audit.json`。原模型为 12598 顶点、15794 三角面、208 骨骼；
检查审计和渲染贴图后再执行 IK。Blender/导入器差异可能改变导出结果，因此重新导出的文件
不一定匹配历史原生导出 SHA；不要把新导出的文件伪称为通过原输入文件校验。

对于原 episode，可只迁移清单中的 `human-stack-v3/source/` 与
`human-natural-v4/human-animation.npz`，其余原生资产由此步骤生成。
`prepare_workspace.py` 已补齐编码所需的历史版权来源和相机构图说明；
IK、动作验证、蒙皮和视频验证 JSON 由各步骤重新生成。

## 实际验证范围

此前完成的是独立恢复后的验证：186954 个条目校验、USD 引用重定位、
原 1507 帧中三帧双视角重渲染，以及当前仓库源码完整机器人任务运行。
见 [渲染记录](../provenance/migration-render-verification.json)、
[机器人记录](../provenance/migration-robot-stack-validation.json)。
这不等于已执行一遍全新联网安装，更不代表任意新任务的自动人体转换已完成。
旧快照恢复工具另见 [OFFLINE_SNAPSHOT.md](OFFLINE_SNAPSHOT.md)，不是默认迁移流程。
