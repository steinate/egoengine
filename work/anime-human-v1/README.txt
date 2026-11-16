Amber / 安柏：原机械臂任务的同步人物演示

原任务：InternDataEngine 官方 pipeline 生成、带此前已记录的任务级 stable_place 修复的双臂叠块和抬托盘 episode。
完整时间轴：1507 帧，15 fps，100.466667 秒。左手抓放、右手叠放、撤手、双手抬托盘、末尾保持全部保留。
原始 world-tracks.npz SHA256：ffe2178587c9dcb770c28e528bb3d76f2e48bf7d693eb20858f8073cc4d6c655

视频：
robot-ego-front-full.mp4：左为原机器人视频，中为安柏 ego，右为安柏正面全身。
amber-ego-full.mp4、amber-front-full.mp4：1280x720 单视角版本。
三路按同一源帧索引拼接，不重采样、不跳过任务段、不改变物体位姿。

人物：安柏2.0 PMX，版权 miHoYo，模型编辑 神帝宇。
下载地址：https://activity.hdslb.com/blackboard/static/20210316/4d40bc4f98f94fbc71c235832ce3efd4/ApoSncaZI8.zip
下载索引：https://mmdfr.fr/genshin-mmd/
原生模型 12598 顶点、15794 三角面、208 骨骼；使用原 UV、原贴图、原蒙皮权重。
整体统一缩放 1.10，左右上臂约 0.2563m、前臂约 0.2183m。各骨段长度在动画中保持不变。
模型附带使用条款禁止商用和二次分发；本包不含 PMX、贴图、Blender 模型或网格缓存。此资产未获商业训练许可。

IK：
从上一版人物的空间接触位置提取参考，不读取机械臂关节角作为人物关节角。
用安柏原生手骨建立每手 17 DOF 的有界 IK，拟合接触目标；再用原生臂长求双骨 IK。
按用户最新要求，全程骨盆和脊柱保持固定直立，躯干前倾角为 0。
站位为 x=0.10m、y=-0.582m，脚下支撑参考面 z≈-0.4664m，允许与桌脚基面有高度差。
使用原生锁骨关节配合双臂 IK，双脚固定在该支撑面，肘部朝外。
手腕旋前分配到原生前臂扭转骨。长发根部保持原生绑定，使用重力方向近似，未运行头发物理。
ego 相机锚定她的原生双眼中心，固定人体右轴，避免垂直俯视时 180 度翻转。
正面视角保留全身；ego 隐藏自己的头和头发。

渲染：Isaac Sim 4.1 RTX PathTracing，64 SPP。使用原场景移除机器人后接入人物。
每个视角单独进程渲染，避免切换可见性产生滞留。原光源强度沿用此前人物版本的 0.18 倍。
材质使用原纹理转换为 USD Preview Surface；这不是游戏原版专用 toon shader 的逐像素复刻。

边界：这是保持原物体轨迹的视觉配对重放，不是重新验证过的人体接触动力学仿真。
手指接触、衣物和长发仍可能有局部轻微穿插；不宣称零碰撞或经人类动作数据训练的控制策略。

配对数据：paired-world-trajectories.npz 保留源轨迹所有字段，另含 source_frame、video_time_s、
左右手 17 DOF、左右手掌规范坐标的世界变换、ego 相机世界变换和内参、正面相机变换和内参。
坐标使用世界米制、列向量 4x4；相机采用 USD 的 -Z 前向、+Y 向上。

复现顺序：
1. import_amber.py / export_native.py：Blender + MMD-Blender/blender_mmd_tools 导入和导出原生资产。
2. solve_motion.py：本模型的手、手臂、躯干、脚和头部解算；verify.py 检查长度、脚稳定性、相机及源轨迹。
3. bake_and_template.py：创建 USD 原生贴图网格和逐帧蒙皮缓存。
4. render_full.sh：在 VLA-Infra 上渲染 ego/front 并编码、核对完整帧数。
工作目录：/vepfs/public/pengjiaqi/interndata-human-pair/anime-human-v1
