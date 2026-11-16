# 部署与复现

本项目直接在 InternDataEngine 基础上开发。根目录保留完整上游代码和 19 个上游提交，
1786 个原始文件没有缺项；新增与修改代码也在同一仓库内。

## 当前方式：代码 + 下载链接

模型、场景素材、安装包等大文件只提供 [下载链接与版本说明](../ASSETS.md)，
以及 [逐文件地址和散列清单](../provenance/interndata-asset-downloads.json)。
不自动打包、下载或传输这些资产。无需重新下载已有的 VLA-Infra 部署。

- 引擎：根目录的 `nimbus/`、`workflows/`、`configs/` 和 `human_pair/`。
- Planning：`deps/curobo/` 保留实际部署的 Python/CUDA 源码。
- 人物骨架导入：`deps/blender_mmd_tools/`。
- 机器人任务、人体 IK 与渲染：`work/robot-stack-v2/`、`work/anime-human-v1/` 等阶段目录。

## 使用现有部署执行当前仓库源码

已验证的环境是 Isaac Sim 4.1.0、Python 3.10、PyTorch 2.2.2+cu118、CUDA 11.8，
运行在 Ubuntu 24.04.2 / NVIDIA L20 / 驱动 535.154.05。详细包版本见
[运行环境审计](../provenance/migration-runtime-audit.json)。

在 Linux 上，从本仓库根目录运行：

```bash
PAIR=/vepfs/public/pengjiaqi/interndata-human-pair
bash migration/run_engine.sh "$PAIR" -m unittest human_pair.test_geometry
bash migration/run_engine.sh "$PAIR" "$PAIR/robot-stack-v2/run.py" --trial migration-trial --seed 42
```

该入口使用当前 Git 根目录的引擎代码，连接已有运行环境，并建立与原部署相同的
`workflows/simbox/{assets,curobo,panda_drake}` 软链接。它不会下载文件，也不会覆盖已有的不同链接。
CuRobo 使用已部署的编译扩展；修改其 CUDA 源码后需要重新编译，不能继续把旧二进制当作新实现。

## 原轨迹的人物视频

```bash
PAIR=/vepfs/public/pengjiaqi/interndata-human-pair
bash "$PAIR/human41/usd_python.sh" "$PAIR/anime-human-v1/verify.py"
bash "$PAIR/anime-human-v1/render_full.sh"
```

原任务有 1507 帧。保持严格配对需要原场景、轨迹、接触参考和同一角色的导出数据，
其已有位置见 [ASSETS.md](../ASSETS.md#本项目生成的数据没有公共下载链接)。
下载一个通用人物模型不能代替这些项目产物。
原生 PMX 导入/导出、人体 IK、烘焙和渲染顺序见
[安柏流程说明](../work/anime-human-v1/README.txt)。

## 已完成的复现验证

- 从已有快照独立恢复并逐文件校验，恢复 186954 个条目。
- 在不同目录运行，USD 所需资产全部解析到恢复副本，原物体轨迹保持一致。
- 渲染原时间轴的第 0、780、1506 帧 ego 和正面视角，位置误差为 0。
- 从离线 Git bundle 克隆仓库，使用仓库根目录引擎源码重新完成双臂叠块、抬托盘和保持。
  新运行包含 1522 个记录帧，独立几何验收通过；它没有替换原来的 1507 帧配对数据。

验证记录见 `provenance/migration-render-verification.json`、
`provenance/migration-restored-runtime-audit.json` 和
`provenance/migration-robot-stack-validation.json`。

此前已经生成的服务器备份与可选恢复工具仍保留，见 [离线快照说明](OFFLINE_SNAPSHOT.md)。
这是可选方案，不是新的下载任务；本次不再传输资产包。
