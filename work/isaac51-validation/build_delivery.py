"""Assemble a local, model-weight-free verification deliverable."""

from pathlib import Path
import json, statistics, shutil, zipfile, hashlib

cwd = Path("/Users/steinate/Documents/Codex/2026-11-12/wo-x")
out = cwd / "outputs/isaac51-validation"
src = cwd / "work/isaac51-validation"
checks = json.loads((out / "delivery-check.json").read_text())
upper = checks["mixed-upperlimb"]["render"]
assert upper["frames"] == 31 and upper["arm_included"] and upper["native_gaussian"]
assert upper["max_position_error_m"] == 0 and upper["max_rotation_error_rad"] == 0
shutil.copy2(
    cwd / "outputs/isaac41/human-ego/official-source-check.json", out / "official-source-check.json"
)
shutil.copy2(
    cwd / "outputs/isaac41/official-dual-grasp/reproduce-and-data-guide.txt",
    out / "original-official-task-provenance.txt",
)
median = statistics.median(upper["render_frame_seconds"])
report = f"""Isaac Sim 5.1 原生 Gaussian / 网格混合渲染验证
验证日期：2026-11-12；运行机器：VLA-Infra。

结论
已生成可播放的 960×540、31 帧、5 FPS、6.2 秒原生混合渲染视频，覆盖手指闭合与方块抬起。方块抬高约 17.2 cm。
原生 NuRec 与普通网格共同出现在同一相机输出中；动态形变通过逐帧切换 NuRec 资产实现。
这验证了渲染与轨迹重放路径可行，不代表完整 InternDataEngine 已迁移到 5.1，也不代表照片级视觉质量已达标。

1. Gaussian 官方资源验证：通过公开替代资产验证，未复现受限数据集原样样例。
NVIDIA 官方公开 flowers_1.zip（562,974 个 Gaussian）通过未修改的上游 3DGRUT NuRec 序列化模块转换后加载。
加入普通红色网格方块，输出 gaussian-and-cube.png；另存 cube-only.png、gaussian-only.png 作可见性对照。
关闭 Gaussian 后，202,378 像素的 RGB 平均绝对差超过 5/255。
使用的是 5.1 的 NuRec UsdVol.Volume / OmniNuRecFieldAsset 路径，不是最新文档中的 ParticleField3DGaussianSplat。
PhysicalAI-Robotics-NuRec 数据集需要 Hugging Face 登录并接受访问条款；本次未下载，不能声称跑过其中原装场景。

2. 官方物体轨迹重放：数值与简化场景画面通过；完整旧场景迁移未通过。
源数据来自官方 Split Aloha stack_cubes_lift/lr、seed 42 的 4.1 成功 episode，抽取 source frame 420..510。
三个物体共 91 帧，逐帧写入世界位姿后，再读取 USD 的世界矩阵核对：最大位置误差 0 m，最大旋转误差 0 rad。
场景采用源记录中的物体网格，重建桌面和简化材质。原始完整 USD 场景在 5.1 中 RGB 仍黑屏，根因尚未确认。
因此不能用数值一致性宣称原场景外观或整个官方任务 Pipeline 已迁移。
5.1 阶段没有重新规划抓取、没有重新仿真物体接触；物体轨迹来自 4.1 官方 Pipeline，手和袖管是自定义重定向与渲染层。
上游关键任务/技能文件的哈希核对附于 official-source-check.json；既有环境兼容性修复见 original-official-task-provenance.txt。

3. 静态 GHOST 对照：轮廓与颜色接近，但转换有近似。
相同相机、相同 4 个姿态、相同 SH degree 0 设置，与原始 GHOST diff-surfel renderer 比较。
轮廓 IoU：96.88%–97.57%；原始手部前景内 RGB 平均绝对误差：6.61–8.33/255。
hand-comparison.png 为同区域裁切并排图；没有对比图后期调色。
GHOST 是 2DGS；当前转为法线方向标准差 0.1 mm 的薄 3D Gaussian，并非无损转换。
没有验证高阶 SH 的等价性。原生混合场景另做隐藏手/隐藏物体的对照，并检查关键帧；未建立跨渲染器逐像素遮挡或接触误差指标。
这些指标仅衡量转换前后接近程度，不能证明原始 GHOST 人手本身具有照片级真实度。

4. 短动作与连续上肢：技术原型通过，生产效率和真人质量未通过。
使用 31 个形变状态，对应源帧 420,423,...,510。5 FPS 保持原始 15 FPS 参考视频的时间尺度。
手指关节间距变化约 7.28 cm（最大关节对距离变化），排除了仅对整个手进行刚性平移旋转的情况。
手腕最大位移约 11.8 cm，肘部约 8.4 cm；肩部固定，前臂和上臂由连续程序化袖管连接，跟随已有 IK。
袖管是普通网格，不是扫描人体、SMPL-X 或可变形 Gaussian 全身模型；腕口仍有可见接缝，手部与衣物质感不够真实。
当前每帧更新流程中位耗时 {median:.2f} 秒，包括资产加载、预热、渲染和读回，并非纯 GPU 渲染基准；验证期间有其他诊断运行。
当前实现预先导出各帧 NuRec 再切引用，尚未证明高效原位更新 Gaussian buffer。此路径适合离线验证，不宜直接当成大规模生产方案。

交付内容
native-gaussian-upperlimb-validation.mp4：主结果，Gaussian 手 + IK 连续袖管 + 网格物体，31 帧。
native-gaussian-grasp-validation.mp4：同一短动作，仅手部，供分辨袖管影响。
official-trajectory-replay.mp4：91 帧物体轨迹重放，15 FPS。
official-object-trajectories.npz / .csv：三个物体的原始 91 帧世界矩阵，米，列向量约定。
*-camera.json：K 和 T_world_camera_opencv；相机右/下/前。
delivery-check.json：视频解码帧数、尺寸、原始帧哈希、非黑屏统计、逐帧耗时和位姿核对。
motion-audit.json：关节形变和物体抬升量；mixed-visibility-check.json、upperlimb-visibility-check.json：可见性对照。
timestamp-notes.txt：时间轴语义。没有原始硬件/记录器逐帧时间戳；nominal_physics_time_s = source_frame/30 只是名义值，不能当作实测时间戳。
validation-code-and-results.zip：本次脚本、版本清单和验证结果，不包含 MANO、GHOST 权重或派生 NuRec 权重。

部署与复跑（依赖 VLA-Infra 现有资产、GHOST 环境及既有轨迹；不是全新机器一键安装包）
远端工作目录：/vepfs/public/pengjiaqi/interndata-human-pair/validation51
Isaac Sim：5.1.0-rc.19+release.26219.9c81211b.gl；GPU：L20；实际驱动：535.154.05。
未升级共享驱动。验证通过仅说明本机这些用例可运行，不代表该驱动组合是官方推荐配置。
所有新缓存与输出放在 validation51；原 4.1 轨迹保留。

cd /vepfs/public/pengjiaqi/interndata-human-pair/validation51
bash run51.sh probe51.py --mode flowers
bash /vepfs/public/pengjiaqi/interndata-human-pair/gaussian-ego/run_gaussian.sh export_ghost.py --all
bash run51.sh probe51.py --mode replay --frames 91 --isolated
bash run51.sh probe51.py --mode hand --color-fix
bash run51.sh probe51.py --mode mixed --isolated --color-fix
bash run51.sh probe51.py --mode mixed --isolated --color-fix --arm --reuse-assets --tag upperlimb
bash run51.sh audit_motion.py
bash run51.sh package_results.py

运行 probe51.py 会覆盖对应 mode 的验证输出，复跑前应保留需要的结果。成功依据为新生成 result.json、非黑屏图片和最终 DELIVERY_VALIDATED，而不是仅看进程退出码。

后续优先事项
先解决完整旧场景黑屏与材质/光照一致性，再做 Gaussian 原位动态更新性能验证。
视觉真实度应单独改进：需要质量更高、覆盖手腕与前臂的可驱动真人资产、连贯纹理和合理接触姿态；仅升级 Isaac Sim 不能补足现有 GHOST 资产质量。

来源与版本
版本提交和许可证记录见 source-manifest.json。
https://docs.isaacsim.omniverse.nvidia.com/5.1.0/assets/usd_assets_nurec.html
https://github.com/nv-tlabs/3dgrut/blob/main/threedgrut/export/README.md
https://github.com/ATAboukhadra/GHOST
https://developer.download.nvidia.com/ProGraphics/nvpro-samples/flowers_1.zip
花卉原作者 Jean-Eudes Marvie https://jmarvie.com；下载包附带许可证为 CC BY 4.0；本次进行了 NuRec 格式转换并与测试方块共同渲染。
"""
(out / "validation-report.txt").write_text(report)
names = ["probe51.py", "run51.sh", "export_ghost.py", "package_results.py", "audit_motion.py"]
with zipfile.ZipFile(out / "validation-code-and-results.zip", "w", zipfile.ZIP_DEFLATED) as z:
    for name in names:
        z.write(src / name, "code/" + name)
    for path in sorted(out.iterdir()):
        if path.suffix in [".txt", ".json", ".csv", ".npz"]:
            z.write(path, path.name)
    z.write(out / "static-hand/result.json", "static-hand/result.json")
manifest = {}
for path in sorted(out.iterdir()):
    if path.is_file() and path.suffix in [".mp4", ".npz", ".csv", ".zip"]:
        manifest[path.name] = {
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
(out / "download-checksums.json").write_text(json.dumps(manifest, indent=2))
print("LOCAL_DELIVERY_READY", list(manifest))
