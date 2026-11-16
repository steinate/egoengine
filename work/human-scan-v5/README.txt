DRL 扫描手对应完整机器人任务的 Human ego 预览

VLA-Infra 工作目录：
/vepfs/public/pengjiaqi/interndata-human-pair/human-scan-v5

本轮资产：Digital Reality Lab Hand Scan Sample。
官方下载：https://www.digitalrealitylab.com/wp-content/uploads/SampleScans/Sample_Hand_CleanScan.zip
供应商与使用说明：https://www.digitalrealitylab.com/sample-model/
原 ZIP：513279033 字节，SHA256：
ba6e61d87e10f2fbfcaea61ed2a58be76071ae4dafcbb7ab59d55e1fd9bb865d

实际文件与网页标称不同：包内颜色图是 8192×8192，不是 16K。
原始 OBJ 有 10488721 个顶点；反细分后保留 164015 个顶点及原 UV。
提取手和袖口区域后，每只手的变形缓存包含 79522 个顶点。
只获得一只扫描手，另一侧使用镜像；没有取得 CC5 HD 全身资产。
完整身体、衣服及已优化的人体上肢 IK 沿用现有 Worker，替换其双手可见网格。

方法：
- 用扫描几何估计关节中心，建立独立的 17 自由度手部模型。
- Blender 骨骼热扩散得到连续蒙皮权重，CPU 双四元数蒙皮避免硬分区折叠。
- 用旧人体的空间接触参考初始化，再按扫描手自己的骨长拟合。
- 平滑手指角度，并用实际拇指表面修正方块接触；托盘使用五个盒子近似墙壁。
- 手腕与前臂连续过渡，裁掉袖口内过长的扫描前臂，隐藏原来的手部面片。
- Isaac Sim 4.1 RTX PathTracing（64 SPP、1280×720），OmniSurface 皮肤材质，保留真实扫描颜色图。
- 物体位姿和时间轴不重新仿真；这是几何重定向和渲染，不是人体 PhysX 抓取。

对应源任务：
../human-stack-v3/source 的 1507 帧、15 fps，编码时长 100.4667 秒。
流程：左手抓放方块、右手抓放方块、撤手、双手抬托盘、保持至最后一帧。
来源是 InternDataEngine 官方管线，并包含此前记录的任务局部 stable_place 修正。
保留原场景、三个物体的全部世界位姿、原机器人视频、帧号、接触事件。
本轮身体未更换，ego 相机沿用已验证的人体眼部相机轨迹；正面相机用于检查身体。

复现顺序：
1. human41/usd_python.sh ../human-scan-v5/prepare_replay.py
2. Blender 执行 import_scan.py、export_scan_mesh.py
3. usd_python.sh export_rig_input.py 导出 rig-input.npz，Blender 执行 heat_weights.py
4. usd_python.sh drive_scan.py --preview：拟合手指并做时序平滑
5. usd_python.sh refine_contact.py：从 scan-animation-before-contact.npz 做方块接触修正
6. usd_python.sh refine_tray.py：在上一步结果上做托盘接触修正（不可重复累加）
7. usd_python.sh make_templates.py
8. bash bake_full.sh；usd_python.sh verify_cache.py
9. bash render_full.sh；usd_python.sh encode.py；usd_python.sh package_delivery.py
   使用持久网格、单个采集相机切换两个视角，先用 1 SPP 的同步帧刷新可见性，再采集 64 SPP 的交付帧。

配对轨迹字段：
- source_frame 为原视频的零起始帧号；video_time_s = source_frame / 15。
- 三个物体的 *_world 为原始世界坐标齐次变换，4×4、平移单位米；原数组逐项保留。
- L_wrist_world / R_wrist_world 为扫描手局部坐标到世界坐标的变换。
- L_q / R_q 为各 17 个关节参数，单位弧度。前五项：拇指根部旋转向量三维、两级屈曲；
  后十二项依次为食指、中指、无名指、小指，每指外展、MCP 屈曲、PIP 屈曲，DIP = 0.65×PIP。
- camera_world_usd 为 ego 相机坐标到世界坐标的变换，相机朝本地 -Z，图像上方为本地 +Y。
- ego_camera_K / front_camera_K 对应两个 1280×720 独立视频的内参；front_camera_world_usd 为正面相机的固定外参。
- 接触事件及场景坐标定义见 contact-schedule.json 和 scene-meta.json。

代码包是 VLA-Infra 现有部署上的复现入口，依赖 ../human41、../human-natural-v4、
../human-stack-v3/source、Isaac Sim 4.1 和单独取得的扫描资产；不包含供应商人物模型。

检查：
replay-contract.json 固定原文件 SHA256，并逐数组核对原任务轨迹。
每个缓存帧保存 source_frame、动画 SHA256、权重 SHA256、变形代码 SHA256。
verify_cache.py 检查全部 1507 帧、有限坐标、法线和相邻帧位移。
encode.py 仅接受完整无重复的帧号，并检查渲染时物体位置/旋转误差小于 1e-6。
最终使用 ffprobe 实际解码计数核验视频帧数和帧率。

边界：
关节中心为几何估计；接触检查不是精确软组织、力学或完整人体碰撞验证。
scan-fit-report 的指尖误差来自表面接触修正前的参考点拟合，不能当作最终表面误差。
surface-contact-report 与 tray-contact-report 只覆盖记录的代表帧及几何近似。
源模型没有提供独立粗糙度/法线/置换贴图，本轮未伪造这些扫描通道。
这是一版实际可驱动的扫描手预览，不能宣称已经达到照片级真人。
目视检查仍能看到部分姿态的掌根和拇指根部鼓起、关节形变不够自然；
静态扫描缺少多姿态修形，热扩散蒙皮和双四元数蒙皮不能自动恢复真实软组织形变。

署名：Hand scan asset courtesy of Digital Reality Lab / HumanScanRepository。
官网说明样例可用于署名的研发和动画，禁止在其他网站再分发模型及衍生模型。
交付视频和代码，不打包再分发该扫描模型。现有 Worker 样例本身仍有使用限制；
本预览不意味着整套资产已取得 VLA 训练/公开数据集用途的全部授权。
