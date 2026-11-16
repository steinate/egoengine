# InternDataEngine 完整迁移

EgoEngine 直接以 InternDataEngine 为基底。上游提交
`2a0a21f2c836df97c925729084e13d68950b4deb` 及其历史已经合并到本仓库，
原有 `nimbus/`、`workflows/`、`configs/`、`deps/`、`policy/` 和 `tests/` 均在根目录。
我们对记录器、控制器、USD 场景导出和轨迹重放的修改直接保留在原代码中。
`human_pair/` 是新增引擎模块，`work/` 保存人物和视频流程。不是重新实现一个引擎。

## 迁移材料

公开 Git 仓库保留完整引擎源码、实际使用的 CuRobo 规划源码及 CUDA 内核
（`deps/curobo/`）、MMD 导入器源码（`deps/blender_mmd_tools/`）、任务配置、人物 IK、
资产转换、同步渲染代码、校验脚本和版本记录。

人物模型的条款禁止公开二次分发，因此按照用户选择，资产与运行环境保存在私有包：

| 目录 | 内容 |
| --- | --- |
| `reproduction/` | 可运行的 Isaac Sim 4.1 部署：引擎、CuRobo 源码与编译扩展、Python/CUDA/GCC 环境、机器人/人物/场景素材、原始轨迹、任务计划、人物参考动作、蒙皮缓存和渲染预热缓存 |
| `local-additions/` | 本机原始 PMX、贴图、Blender 工程、扫描手原始文件、资产导入工具和本机源码；补充服务器上未保存的输入 |
| `system-support/` | 原 Ubuntu 系统的用户态共享库、FFmpeg/FFprobe、Blender、字体和软件包版本清单 |
| 服务器 `bundle/` | 未筛选的完整原部署备份，包括历次渲染图片、日志、缓存和重复下载包 |

每个组件有 `.tar.gz`、逐文件 `.files.jsonl` 和 `.summary.json`；`*-index.json`
记录组件 SHA256、大小及文件清单 SHA256。下载结束逐包校验；恢复时再次校验归档和逐文件内容。
`reproduction/` 中 `MIGRATION-SELECTION.json` 逐项记录省略的重复或可再生成输出。
原始模型、输入轨迹、场景、当前安柏蒙皮缓存、运行环境均保留。

服务器存放目录：`/vepfs/public/pengjiaqi/egoengine-migration-20261116/`。
本机存放目录：项目根目录下 `migration-private/`，由 Git 忽略，不上传公开仓库。
应连同本仓库一起迁移这些私有目录。仅克隆公开仓库无法合法获得受限人物模型，也不是完整运行环境。

## 恢复

目标平台为 Linux x86_64；原环境是 Ubuntu 24.04.2、NVIDIA L20、驱动 535.154.05、
Isaac Sim 4.1.0、Python 3.10。GPU 驱动和内核必须由目标机器提供，私有包不等于操作系统镜像。
`system-support/` 保留用户态文件用于补齐依赖，不要将它直接覆盖到运行中的 `/usr` 或 `/etc`。
迁移不支持把 Linux CUDA 二进制直接运行在 macOS；本机下载用于保存和转移。

为保留原场景和脚本中的绝对引用，首选恢复到原部署路径。目标目录必须不存在，工具拒绝覆盖：

```bash
python3 migration/restore.py /path/to/private/reproduction \
  /vepfs/public/pengjiaqi/interndata-human-pair

# 本机原始资产另行恢复，不能覆盖服务器已验证的 animation/cache。
python3 migration/restore.py /path/to/private/local-additions \
  /path/to/restored-local-work --prefix local-work

# 只检查归档、不解压：
python3 migration/restore.py /path/to/private/reproduction \
  /unused --verify-only
```

上述恢复不需要 git clone 其他仓库、pip 下载、重新下载模型或下载 Isaac Sim。
完整历史源代码还可以由 `git bundle` 离线迁移，打包后随迁移材料保存。

## 原流程入口

```bash
PAIR=/vepfs/public/pengjiaqi/interndata-human-pair
cd "$PAIR"

# 引擎几何验证
bash run_env41.sh -m unittest human_pair.test_geometry

# 保留已验证的 1507 帧物体轨迹，检查并重渲染人物配对视频
bash human41/usd_python.sh "$PAIR/anime-human-v1/verify.py"
bash anime-human-v1/render_full.sh

# 重新执行机器人规划与物理任务：会生成新 episode，不覆盖原始配对轨迹
bash run_env41.sh "$PAIR/robot-stack-v2/run.py" --trial migration-trial --seed 42
```

绝对脚本路径更稳妥：`run_env41.sh` 会切换到引擎目录，所以调用外部阶段脚本时应传绝对路径。
人物完整重建顺序及脚本见 `work/anime-human-v1/README.txt`：原生资产导入/导出 →
`solve_motion.py` → `verify.py` → `bake_and_template.py` → `render_full.sh`。
`local-additions/` 保留原生模型和转换工程；服务端复现可直接使用已导出的同一原生网格、骨架与贴图。

机器人任务使用官方 pipeline 加已记录的 `stable_place` 修复。
重新做物理规划不能保证 GPU/驱动改变后逐位相同；需要和原机器人视频严格配对时，应重放包内保存的物体轨迹。
人物视频是视觉轨迹配对重放，不是新的人体接触动力学验证。

## 工具

- `build_snapshot.py`：保存权限、软链接、内容校验和，拒绝打包过程中变化的文件。
- `select_reproduction.py`：生成运行副本，并记录每项省略；原始完整备份另存。
- `download_bundle.py`：分块、可续传 SSH 下载，最终核对完整归档 SHA256。
- `restore.py`：拒绝覆盖现有目录，核对归档、逐文件散列与路径。
- `audit_runtime.py`：在实际 Isaac Sim 环境中检查规划器、CUDA、USD 依赖及原物体轨迹。
- `capture_system.py`：保留用户态支持文件与 OS 包版本，排除用户凭据。

本次迁移针对已经完成的 Isaac Sim 4.1 双臂任务与安柏视频。5.1/Gaussian 实验代码和已有文件被保留，
但其在服务器其他位置的独立 5.1 安装不属于这套 4.1 运行环境，不能将其称为已验证的完整 5.1 迁移。
