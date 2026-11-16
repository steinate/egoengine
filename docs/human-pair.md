# Robot → Human Ego 配对视频实验

保存 InternDataEngine 机械臂任务到人物演示视频的源码、配置、部署补丁和验证记录。
物体位姿与时间轴来自机器人 episode；人物使用自己的骨架求解 IK，再在 Isaac Sim 中同步重放。

## 当前已验证版本

`work/anime-human-v1/` 为安柏直立版：1507 帧、15 fps、100.466667 秒，包含双臂叠块、撤手、抬托盘和末尾保持。
人物全程固定直立，脚下支撑面允许与桌脚基面不同高。人物使用原生骨长、手指 IK 和双骨手臂 IK。
机器人、ego、正面视频按同一源帧索引同步。

机器人任务使用 InternDataEngine 官方 pipeline，包含已记录的任务级 `stable_place` 修复；不是未经修改的上游基准。
人物输出是保持源物体轨迹的视觉配对重放，不代表重新验证了人体接触动力学。

- 源轨迹 SHA256：`ffe2178587c9dcb770c28e528bb3d76f2e48bf7d693eb20858f8073cc4d6c655`
- 验证报告：[evidence/amber-upright](../evidence/amber-upright/)
- 实现与复现顺序：[安柏说明](../work/anime-human-v1/README.txt)
- 本机完整视频：`outputs/anime-human-v1/delivery/robot-ego-front-full.mp4`

学园偶像大师人物目前仅进行资产调研，尚未接入或渲染完成。

## 文件组织

保留现有阶段目录，避免移动脚本破坏跨阶段导入和已部署路径。

| 目录 | 内容 |
| --- | --- |
| `work/isaac41/` | Isaac Sim 4.1 环境、官方任务执行、轨迹导出与诊断 |
| `work/robot-stack-v2/` | 完整双臂叠块和抬托盘任务及稳定放置修复 |
| `work/human-stack-v3/` | 原始完整配对 episode 与人物重放入口 |
| `work/human-natural-v4/` | 人体手臂、手指、站姿和相机优化 |
| `work/human-scan-v5/`、`work/human-scan-v6/` | 扫描手接入、原生 UV 和左右手修正 |
| `work/anime-human-v1/` | 当前完成的安柏原生骨架、直立 IK 和同步渲染 |
| `work/human41/`、`work/human-ego/`、`work/human-ik-v2/`、`work/paired-human-ego/` | 早期实现与阶段性验证，保留以便追溯 |
| `work/avatar-assets-v1/` | 人物资产转换与预览工具 |
| `work/gaussian-ego/`、`work/isaac51-validation/` | Gaussian 与 Isaac Sim 5.1 实验，不作为当前交付入口 |
| `patches/` | 本机和 VLA-Infra 的 InternDataEngine 修改，分别保存 |
| `provenance/` | 上游版本、补丁校验和及本机提交信息 |
| `evidence/` | 已完成渲染的只读验证记录 |

## 开发检查

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
make format RUFF=.venv/bin/ruff
make check RUFF=.venv/bin/ruff
```

Ruff 固定为 0.14.4；Python 使用 100 列、四空格、双引号。语法检查不会导入 Isaac Sim 或 Blender。
引擎几何测试需要 NumPy，可在已有科学计算环境中执行：

```bash
cd work/InternDataEngine
python -m unittest human_pair.test_geometry
```

## 部署与复现边界

VLA-Infra 的现有部署根目录为 `/vepfs/public/pengjiaqi/interndata-human-pair`。
仓库的 `work/<阶段>/` 对应部署的 `<根目录>/<阶段>/`；`work/isaac41/` 中环境包装脚本对应部署根目录。
脚本仍包含这套实验环境的固定路径，不能把干净克隆视为已安装好资产与运行环境的一键工程。
引擎补丁用法见 [patches/README.md](../patches/README.md)。

人物解算、Blender 导入、Isaac Sim 渲染分别需要对应运行环境，以及原轨迹、场景、合法取得的人物资产和阶段缓存。
安柏的顺序为导入/导出资产 → `solve_motion.py` → `verify.py` → `bake_and_template.py` → `render_full.sh`。
已有部署上的 `render_full.sh` 还依赖预览阶段预热的渲染缓存；不要盲目覆盖正在使用的部署文件。

本次整理先保存原始源码快照，再单独提交格式化。历史报告中的代码散列指向当时实际执行的文件；
格式化后的源码不冒充重新渲染过的版本。格式化通过 Python AST 等价检查和既有验证脚本核验。

模型、贴图、原轨迹、视频、缓存、下载的第三方仓库及虚拟环境保留在磁盘，由 `.gitignore` 排除。
第三方仓库版本见 [provenance/dependencies.json](../provenance/dependencies.json)，InternDataEngine、CuRobo 与 MMD 导入器源码已直接保存在本仓库；其余实验代码保存在私有迁移包。
安柏资产条款禁止商用和二次分发；代码提交不含原模型或贴图。其他资产遵循各自授权。

本机与部署源码比对时，三个本机诊断/实验脚本比部署更新：`audit_colliders.py` 排除 Cooked 属性、
`measure_recorded_contact.py` 从关节框架推导位移、`gaussian-ego/fit_motion.py` 修正模板 RMSE。
这些本机改动保留；部署代码未被格式化或覆盖。
