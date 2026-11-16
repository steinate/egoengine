# Human ego 转换候选与当前验证边界

下表是按源码任务族整理的接入要求，不代表全部通过人体 IK 或视频验收。规划结果与配对验收分别保留。

| 任务族 | 代表配置结果 | 其他实跑中成功的配置 | 人体重放要求 |
|---|---|---|---|
| art/close_the_electriccooker | runtime_error |  | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
| art/close_the_laptop | planning_failed |  | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
| art/close_the_microwave | planning_failed |  | 已有同任务的独立配对验收 episode；本配置实例仍按本行结果判断 |
| art/close_the_oven | planning_failed |  | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
| art/close_the_package | planning_failed |  | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
| art/close_the_pot | planning_failed |  | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
| art/close_the_trashcan | planning_failed |  | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
| art/close_the_washingmachine | planning_succeeded | art/franka/close_the_washingmachine/close_the_washingmachine_part1.yaml | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
| art/grasp_the_microwave_handle | runtime_error |  | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
| art/heat_the_food_in_the_microwave | runtime_error |  | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
| art/open_the_laptop | planning_failed |  | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
| art/open_the_microwave | planning_failed | art/split_aloha/open_the_microwave/left/open_the_microwave_part0.yaml | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
| art/open_the_microwave_from_scratch | runtime_error |  | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
| art/open_the_oven | planning_failed |  | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
| art/open_the_pot | planning_failed |  | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
| art/open_the_trashcan | planning_failed |  | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
| art/pull_the_storagefurniture | planning_failed |  | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
| art/push_the_storagefurniture | planning_failed |  | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
| basic/arrange_the_tableware | planning_failed |  | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
| basic/conveyor_beef_sandwich | planning_succeeded | basic/lift2/conveyor_beef_sandwich/conveyor_beef_sandwich.yaml | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
| basic/conveyor_ham_sandwich | planning_succeeded | basic/split_aloha/conveyor_ham_sandwich/conveyor_ham_sandwich.yaml | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
| basic/hang_the_cup_on_rack | planning_failed |  | 已有同任务的独立配对验收 episode；本配置实例仍按本行结果判断 |
| basic/insert_the_flower_in_vase | planning_failed |  | 已有同任务的独立配对验收 episode；本配置实例仍按本行结果判断 |
| basic/insert_the_markpen_in_penholder | planning_failed |  | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
| basic/pick_the_package_on_conveyor | planning_succeeded | basic/lift2/pick_the_package_on_conveyor/pick_the_package_on_conveyor.yaml | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
| basic/pour_Baijiu | planning_failed |  | 需额外记录粒子/液体状态；当前刚体转换器不覆盖 |
| basic/pour_coke | planning_failed |  | 需额外记录粒子/液体状态；当前刚体转换器不覆盖 |
| basic/pour_redwine | planning_failed |  | 需额外记录粒子/液体状态；当前刚体转换器不覆盖 |
| basic/pour_water | runtime_error |  | 需额外记录粒子/液体状态；当前刚体转换器不覆盖 |
| basic/recovery_pick_objects | runtime_error |  | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
| basic/sort_the_tary_on_rack | planning_failed |  | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
| basic/sort_the_tray_on_rack | planning_succeeded | basic/split_aloha/sort_the_tray_on_rack/sort_the_tray_on_rack.yaml | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
| basic/stack_bowls | planning_failed |  | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
| basic/stack_cubes_lift | planning_failed | basic/split_aloha/stack_cubes_lift/lr.yaml; basic/split_aloha/stack_cubes_lift/rl.yaml | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
| basic/store_the_eggs | planning_failed |  | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
| basic/store_the_toothbrushes | planning_failed |  | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
| basic/track | planning_succeeded | basic/franka/track/track_the_targets.yaml | 仅目标跟踪，不作为抓取/操作类 Human ego 配对样本 |
| basic/track_the_targets | planning_failed |  | 仅目标跟踪，不作为抓取/操作类 Human ego 配对样本 |
| basic/water_plant | planning_failed |  | 需额外记录粒子/液体状态；当前刚体转换器不覆盖 |
| example | planning_succeeded | example/sort_the_rubbish.yaml | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
| long_horizon/clean_the_dirt_with_brown_cloth | runtime_error |  | 需核对污渍/可见性或材质变化，另适配工具接触 |
| long_horizon/clean_the_dirt_with_sponge | runtime_error |  | 需核对污渍/可见性或材质变化，另适配工具接触 |
| long_horizon/clean_the_dirt_with_white_cloth | runtime_error |  | 需核对污渍/可见性或材质变化，另适配工具接触 |
| long_horizon/collaborate_assemble_a_beef_sandwich | runtime_error |  | 多机器人协作，需要多个人体或角色分工，当前单 Worker 转换器未适配 |
| long_horizon/collaborate_assemble_a_beef_sandwich_mix | runtime_error |  | 多机器人协作，需要多个人体或角色分工，当前单 Worker 转换器未适配 |
| long_horizon/collaborate_assemble_a_ham_sandwich | runtime_error |  | 多机器人协作，需要多个人体或角色分工，当前单 Worker 转换器未适配 |
| long_horizon/dexpnp | planning_succeeded | long_horizon/lift2/dexpnp/sort_parts_0.yaml | 需灵巧手接触及手指映射，尚未完成人体转换 |
| long_horizon/flip_package | runtime_error |  | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
| long_horizon/handover | planning_failed |  | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
| long_horizon/pack_in_objects | planning_failed |  | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
| long_horizon/pack_out_objects | planning_failed |  | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
| long_horizon/put_the_trashcan_in_trashcan | planning_failed |  | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
| long_horizon/sort_the_rubbish | planning_succeeded | long_horizon/lift2/sort_the_rubbish/sort_the_rubbish_part0.yaml | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
| long_horizon/stack_a_beef_sandwich | planning_failed |  | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
| long_horizon/store_objects_in_the_drawer | planning_failed |  | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
| pick_and_place/dual_pnp | planning_failed |  | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
| pick_and_place/single_func_pick | planning_succeeded | pick_and_place/genie1/single_func_pick/left/phocal-red_wine_glass.yaml | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
| pick_and_place/single_pick | planning_succeeded | pick_and_place/franka/single_pick/google_scan-handbag.yaml; pick_and_place/split_aloha/single_pick/left/google_scan-handbag.yaml; pick_and_place/split_aloha/single_pick/left/google_scan-hat.yaml; pick_and_place/split_aloha/single_pick/left/omniobject3d-bamboo_shoots.yaml; pick_and_place/split_aloha/single_pick/left/omniobject3d-banana.yaml; pick_and_place/split_aloha/single_pick/right/google_scan-handbag.yaml; pick_and_place/split_aloha/single_pick/right/omniobject3d-banana.yaml | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
| pick_and_place/single_pnp | planning_failed |  | 候选：保存刚体/连杆状态，新增接触定义并做人体可达性与视野验收 |
