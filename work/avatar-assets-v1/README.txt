数字人替换资产检查（VLA-Infra / Isaac Sim 4.1）

目录：/vepfs/public/pengjiaqi/interndata-human-pair/avatar-assets-v1

已下载并转换：
1. Renderpeople Eric Rigged 001：88 骨骼、10353 顶点、8192x8192 贴图。
2. Renderpeople Carla Rigged 001：88 骨骼、10067 顶点、8192x8192 贴图。
3. Renderpeople Claudia Rigged 002：88 骨骼、10820 顶点、8192x8192 贴图。
官方免费 FBX 包下载地址：
https://renderpeople.com/sample/free/renderpeople_free_rigged_people_FBX.zip
官方介绍：https://renderpeople.com/free-3d-people/
注意：标准/免费许可未覆盖本项目的计算机视觉、数据集生成、模型训练用途。
需要另行获得对应许可。本轮只作资产外观和关节驱动预览，不进入训练数据集。
条款：https://renderpeople.com/general-terms-and-conditions/

4. MakeHuman/MPFB：下载官方 CC0 核心资产包与 CC0 skins02 男性皮肤包，
使用 MPFB 生成着装男性，使用 52 骨骼 Mixamo 命名骨架。
本次生成模型使用核心资产中的皮肤、衣服、鞋、头发、眼睛等。
skins02 包也已下载，可用于后续更换皮肤；未将其全部应用到同一人物上。
核心资产包：
https://files2.makehumancommunity.org/asset_packs/makehuman_system_assets/makehuman_system_assets_cc0.zip
男性皮肤包：
https://files2.makehumancommunity.org/asset_packs/skins02/skins02_cc0.zip
许可：https://www.makehumancommunity.org/about/license.html
代码：https://github.com/makehumancommunity/mpfb2
MPFB 程序代码是 GPL，核心资产和本次生成模型输出是 CC0。

已完成的验证：
- FBX/Blender 到原生 UsdSkel 的骨架、蒙皮、贴图转换。
- 读取每个资产自己的关节位置与臂长，独立双臂两连杆 IK。
- 全部 30 个手指关节都有非零顶点蒙皮权重。
- 61 帧 / 15 fps 的手臂和手指驱动测试，约 4.07 秒。
- Isaac Sim 4.1 RTX 全身与手部近景渲染，同一套灯光。
- 4.1 播放沿用已有 CPU UsdSkel 蒙皮后回放网格的路径；原始带骨骼 USD 保留。
- MPFB 体型 shape keys 必须先固化再导出，否则身体与头发/眼睛错位。
  已修复，并将 0/30/60 帧的全部网格与 Blender 求值结果比较，误差 < 0.002 毫米。

验证范围：
这是独立的资产外观与关节驱动预览，没有重放机器人抓取任务、没有生成新的
Human-robot 配对训练数据，也没有验证人体 PhysX 抓取接触。
现有 human-natural-v4 的完整任务和轨迹未修改。

替换完整任务的方法：
保留官方物体世界位姿、时间戳、场景和事件；使用新资产的骨骼映射与真实骨长，
重新拟合掌心/指腹接触模板、肘部自然平面和全程动作平滑，再生成 eye camera。
不能把 Worker 的 101 骨骼角度直接复制给 88 或 52 骨骼资产。
本目录 asset-drive-verification.json 给出了各模型语义骨骼映射、手指权重、IK 误差。

主要文件：
assets/renderpeople/              下载解压后的原始扫描人物 FBX 与贴图
assets/makehuman/                 CC0 核心资产和额外皮肤
converted/*.blend                可编辑的导入/生成模型
usd/<asset>/rigged.usdc           带骨骼和测试动画的 USD
usd/<asset>/visual-template.usdc  4.1 网格回放模板
usd/<asset>/cache/*.npz           CPU 蒙皮缓存
renders/<asset>/                  实际 4.1 渲染帧

观察结论：
Renderpeople 的照片扫描皮肤、面部和衣物纹理适合提高当前人物的外观真实度。
手部仍是低面数实时角色的几何，身体 8K 贴图不等于独立 8K 手部细节。
MPFB 更适合许可清晰、可程序化换体型的训练路线；本次材质转换下近景质感较弱，
不应当宣传成比扫描角色更逼真或已经照片级。

进一步提高近景质量的候选：CC5 HD 高细分角色及 4K/8K 皮肤，需获取相应资产。
https://www.reallusion.com/character-creator/hd-character-base.html
训练用途需要核对 Enterprise 等专项许可：
https://www.reallusion.com/license/content.html
当前旧 Worker 样例包自身的 Readme 也限制商业/生产用途，不能默认当作已获训练许可。

其他搜索结果：3DPeople 的 Vivian 免费 rigged 资产提供 40k 网格、8K 贴图，
本轮官方下载链接返回 HTTP 403，未下载、未计入验证结果。
https://3dpeople.com/en/free-3dpeople/
