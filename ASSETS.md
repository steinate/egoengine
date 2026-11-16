# 资产和环境下载链接

代码以本仓库根目录的 InternDataEngine 为基底。大模型、贴图、SDK 和数据不放入 Git，
只列来源、版本、目标位置和校验信息；这些链接不会自动触发下载。

## 当前安柏 / Isaac Sim 4.1 流程

| 内容 | 下载入口 | 版本与放置位置 |
| --- | --- | --- |
| Isaac Sim | [NVIDIA 官方下载页](https://docs.isaacsim.omniverse.nvidia.com/latest/installation/download.html) | 使用已验证的 **4.1.0**，解压到部署目录 `runtime41/`；不要直接替换为最新版 |
| 原版机器人、桌面、物体和规划资产 | [InternData-A1 / InternDataAssets](https://huggingface.co/datasets/InternRobotics/InternData-A1/tree/main/InternDataAssets) | 保留目录结构，放到 `assets/InternDataAssets/` |
| 双臂机器人 | [split_aloha_mid_360](https://huggingface.co/datasets/InternRobotics/InternData-A1/tree/main/InternDataAssets/assets/split_aloha_mid_360) | `assets/InternDataAssets/assets/split_aloha_mid_360/` |
| 叠块和托盘 | [basic/stack_lift](https://huggingface.co/datasets/InternRobotics/InternData-A1/tree/main/InternDataAssets/assets/basic/stack_lift) | 同名相对目录 |
| 桌面 | [table0](https://huggingface.co/datasets/InternRobotics/InternData-A1/tree/main/InternDataAssets/assets/table0) | 同名相对目录 |
| 环境光 | [envmap_lib](https://huggingface.co/datasets/InternRobotics/InternData-A1/tree/main/InternDataAssets/assets/envmap_lib) | 同名相对目录 |
| CuRobo 资产和机器人配置 | [curobo](https://huggingface.co/datasets/InternRobotics/InternData-A1/tree/main/InternDataAssets/curobo) | `assets/InternDataAssets/curobo/`；规划器源码已保存在 `deps/curobo/` |
| 机器人 URDF/网格 | [panda_drake](https://huggingface.co/datasets/InternRobotics/InternData-A1/tree/main/InternDataAssets/panda_drake) | `assets/InternDataAssets/panda_drake/` |
| 安柏 2.0 原生 PMX / 贴图 | [原始模型 ZIP](https://activity.hdslb.com/blackboard/static/20210316/4d40bc4f98f94fbc71c235832ce3efd4/ApoSncaZI8.zip) | 解压到 `anime-human-v1/assets/amber/`；保留原始贴图目录 |
| Blender 5.2.2 | [Linux x64](https://download.blender.org/release/Blender5.2/blender-5.2.2-linux-x64.tar.xz)、[macOS ARM64](https://download.blender.org/release/Blender5.2/blender-5.2.2-macos-arm64.dmg)、[官方 SHA256](https://download.blender.org/release/Blender5.2/blender-5.2.2.sha256) | 原 PMX 转换在 macOS 5.2.2 完成；MMD 导入器要求 Blender ≥4.2，源码已在 `deps/blender_mmd_tools/` |
| CUDA 11.8 构建组件 | [NVIDIA 11.8.0 分发清单](https://developer.download.nvidia.com/compute/cuda/redist/redistrib_11.8.0.json) | 原环境使用 CUDA 11.8；清单包含组件地址和 SHA256 |

安柏原始 ZIP 的 SHA256：

```text
4dafd2bc1251d7c90cc68e62fd3edda29aa137ae430dc382df19d44859ce52f5
```

原模型版权与使用条件保留在 [provenance/amber 记录](evidence/amber-upright/provenance.json)，
包含禁止商用、禁止二次分发的原文。模型本体不随公开 Git 仓库分发。

**Isaac Sim 4.1 的公开旧版 ZIP 直链未确认可用。** 官方下载页可能只提供较新版本，
不能把它们视为本项目的已验证替代。VLA-Infra 已有安装包
`/vepfs/public/pengjiaqi/interndata-human-pair/downloads/isaac-sim-4.1.0.zip`
和完整 `runtime41/`，需要迁移时可按需复用；当前不自动传输。

## 逐文件地址与完整性

[interndata-asset-downloads.json](provenance/interndata-asset-downloads.json)
列出此前实际选取的 **1578 个文件**的下载 URL、大小、所属清单和上游散列。
其中包含早期单臂任务、干扰物及规划器文件，不要求全部下载，更不要求下载整个 InternData-A1 数据集。
按对应任务的清单组选择即可。

URL 使用上游 `main` 分支，它可能变化。LFS 文件应核对记录的 `upstream_lfs_sha256`；
`git_blob_oid` 是 Git blob 标识，不是文件 SHA256。不要只根据同名文件或文件大小判断版本相同。

## 早期/可选人物资产

- Digital Reality Lab 扫描手：[Sample_Hand_CleanScan.zip](https://www.digitalrealitylab.com/wp-content/uploads/SampleScans/Sample_Hand_CleanScan.zip)，[供应商下载页](https://www.digitalrealitylab.com/sample-model/)。本次仅检查 HTTP 头，直链返回 403；需要浏览器或供应商授权链接，不能保证匿名命令行可下载。
- MakeHuman：[CC0 核心资产](https://files2.makehumancommunity.org/asset_packs/makehuman_system_assets/makehuman_system_assets_cc0.zip)、[skins02](https://files2.makehumancommunity.org/asset_packs/skins02/skins02_cc0.zip)。
- Renderpeople：[免费带骨骼 FBX 示例](https://renderpeople.com/sample/free/renderpeople_free_rigged_people_FBX.zip)，[官方说明](https://renderpeople.com/free-3d-people/)。历史资产预览与用途限制见 `work/avatar-assets-v1/README.txt`；它不是当前安柏流程的必需输入。

## 本项目生成的数据没有公共下载链接

下载通用模型不能替代同一 episode 的轨迹与接触参考。要严格复现原来的 **1507 帧**配对视频，
需使用 VLA-Infra 部署目录 `/vepfs/public/pengjiaqi/interndata-human-pair/` 内已有文件：

- `human-stack-v3/source/`：原物体轨迹、场景、机器人视频和时间轴。
- `robot-stack-v2/delivery/`：机械臂轨迹导出和验证记录；其中有下游脚本的输入，不能当作纯视频输出丢弃。
- `human-natural-v4/human-animation.npz`：人物接触参考。
- `anime-human-v1/`：原生导出网格/骨架、材质、贴图、IK 动作与蒙皮缓存。

这些是本项目产物，不虚构公开 URL，也不在本次继续下载。原轨迹 SHA256 为
`ffe2178587c9dcb770c28e528bb3d76f2e48bf7d693eb20858f8073cc4d6c655`。
可以从已有服务器按需取得指定文件，或运行仓库中的导出、IK 和烘焙步骤重新生成。
重新进行物理规划可能产生不同帧数的新 episode，不能声称与原 1507 帧逐位一致。
