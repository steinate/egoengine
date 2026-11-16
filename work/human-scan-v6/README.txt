DRL 原生扫描手对接修正版（人物不变）

VLA-Infra：/vepfs/public/pengjiaqi/interndata-human-pair/human-scan-v6

本轮修正：
1. 原 ZBrush OBJ/PNG 组合的纹理方向需要 (u,v)->(u,1-v)。此前指甲、掌纹与毛发贴错位置。
2. 原扫描资产为右手。上一版左右镜像与掌背方向用反；本版右手保留原手性，左手镜像。
3. 将手背与人物手背方向对齐，重新拟合手指并修正接触，使正向屈曲朝掌心。

保留人物：身体、衣服、肩肘腕运动、ego/正面相机沿用原已验证轨迹。
保留任务：1507 帧、15 fps、100.466667 秒，物体位姿逐项保留，不重新模拟物体。
源任务来自 InternDataEngine 官方管线及此前已记录的 stable_place 局部修正。
这是可视化重定向回放，不是新的人体物理抓取仿真。

资产：Digital Reality Lab / HumanScanRepository。
官方下载：https://www.digitalrealitylab.com/wp-content/uploads/SampleScans/Sample_Hand_CleanScan.zip
原始颜色图：Sample_Hand_Diffuse.png，8192×8192，文件未改写或重画。
保留扫描网格派生的减面版本、原始 UV 拓扑；每只手 79522 个缓存顶点。
模型连接到原人物的腕部，袖口内部的多余扫描前臂面隐藏。
ZIP 未附所引用的 MTL，因此没有可直接照搬的供应商完整着色器；使用原颜色图和 OmniSurface。
没有取得/替换 CC5 全身模型，也没有把扫描颜色图贴到原人物手网格上。

实现：
- setup_native_hands.py：右手/左手镜像、UV V 修正、原生几何回转校验、掌侧屈曲方向校验。
- hand_model.py：扫描骨长的 17 自由度手；既有热扩散权重在整体镜像下保持对应。
- drive_scan.py：空间指尖拟合及时序平滑，完整 1507 帧缓存。
- refine_contact.py / refine_tray.py：按实际蒙皮表面修正代表帧的方块、托盘接触。
- render.py：Isaac Sim 4.1 路径追踪，1280×720、64 SPP；低采样同步步骤后采集最终画面。
- encode.py / package_delivery.py：验证全帧序列、原物体轨迹、渲染脚本版本，编码和打包。
- audit_native_scan.py：用原扫描的未变形形状核对手背、指甲、掌纹与 UV，不用于任务视频。

复现顺序（现有 VLA-Infra 部署）：
在 human41 下用 usd_python.sh 执行 setup_native_hands.py、drive_scan.py --preview、
refine_contact.py、refine_tray.py，然后执行 bake_full.sh、finish_delivery.sh。
refine_contact.py 从 scan-animation-before-contact.npz 恢复基线；重新拟合后须更新该基线。
refine_tray.py 在方块修正后执行一次，不重复累加。
依赖 ../human-scan-v5 的合法下载扫描资产、原模型预处理结果/热扩散权重、
../human-natural-v4 的人体动画与身体缓存、../human41 与 Isaac Sim 4.1。

数据字段：
source_frame 是零起始帧号；video_time_s=source_frame/15。
物体 *_world 为 4×4 世界坐标变换，平移单位米，原数组逐项保留。
L_wrist_world / R_wrist_world 为手局部到世界的变换。
L_q / R_q 为各 17 个手指参数，弧度：拇指根部旋转向量三维加两级屈曲，
随后食指、中指、无名指、小指各外展、MCP、PIP，DIP=0.65×PIP。
camera_world_usd 为 ego 相机到世界变换；相机本地 -Z 朝前、+Y 朝上。
ego_camera_K / front_camera_K 对应独立 1280×720 视频；front_camera_world_usd 为固定正面相机变换。

验证与边界：
native-hand-verification.json 验证扫描原始坐标的可逆对应和掌侧屈曲方向。
cache-verification.json 检查全部帧、动画/权重/变形代码哈希及有限坐标。
video-verification.json 记录实际解码帧数、相机、物体位姿误差。
接触报告覆盖代表帧及盒子近似，不代表完整碰撞、软组织或力学验证。
手部骨骼与蒙皮仍是本地建立的近似绑定，并非供应商提供的多姿态修形 rig。

署名：Hand scan courtesy of Digital Reality Lab / HumanScanRepository。
供应商说明：https://www.digitalrealitylab.com/sample-model/
交付包不再分发供应商原扫描网格或纹理。既有 Worker 资产的使用限制仍适用；
本预览不意味着整套资产已取得 VLA 训练或公开数据集用途的全部授权。
