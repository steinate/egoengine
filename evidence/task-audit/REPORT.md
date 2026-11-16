# 本机官方任务复现审计

测试范围：全部 1128 个 YAML 做依赖检查；59 个源码任务族各选一个原配置执行。没有逐一测试所有机器人、左右臂和物体变体。论文 70 个语义任务与源码目录任务族不是一一对应。

## 实际执行结果

```json
{
  "runtime_error": 13,
  "planning_failed": 35,
  "planning_succeeded": 11
}
```

成功仅表示官方规划 API 返回非零帧数；失败仅表示本次 seed/资产集合未通过。完整物体轨迹、终态与人体视频另行验收，目前配对视频验证的是挂杯、关闭微波炉和插花三项。

另保留最初 25 份配置的实跑与 12 次单独复测。去重后共测试 81 份配置，产生 93 个独立运行目录；合并这些尝试后，13 个源码任务族至少有一份配置返回成功轨迹。这不代表同一族的全部变体都成功。

两项传送带基线尝试曾因超时进程组清理问题发生短暂重叠；修复后另做顺序重测，见 retest-results.json 和 execution-caveats.json。基线保留，不能将其耗时当作干净的串行性能数据。

| 源码任务族 | 实际配置 | 状态 | 帧数 | 异常/阻塞 |
|---|---|---|---:|---|
| art/close_the_electriccooker | art/franka/close_the_electriccooker/close_the_electriccooker.yaml | runtime_error |  | ValueError('Found zero norm quaternions in `quat`.') |
| art/close_the_laptop | art/franka/close_the_laptop/close_the_laptop.yaml | planning_failed | 0 |  |
| art/close_the_microwave | art/franka/close_the_microwave/close_the_microwave_part0.yaml | planning_failed | 0 |  |
| art/close_the_oven | art/split_aloha/close_the_oven/left/close_the_oven_part0.yaml | planning_failed | 0 |  |
| art/close_the_package | art/lift2/close_the_package/close_the_package.yaml | planning_failed | 0 |  |
| art/close_the_pot | art/franka/close_the_pot/close_the_pot.yaml | planning_failed | 0 |  |
| art/close_the_trashcan | art/franka/close_the_trashcan/close_the_trashcan.yaml | planning_failed | 0 |  |
| art/close_the_washingmachine | art/franka/close_the_washingmachine/close_the_washingmachine_part1.yaml | planning_succeeded | 283 |  |
| art/grasp_the_microwave_handle | art/split_aloha/grasp_the_microwave_handle/left/grasp_the_microwave_handle_part0.yaml | runtime_error |  | IsADirectoryError(21, 'Is a directory') |
| art/heat_the_food_in_the_microwave | art/lift2/heat_the_food_in_the_microwave/heat_the_food_in_the_microwave.yaml | runtime_error |  | KeyError('offset_place_obj_axis') |
| art/open_the_laptop | art/franka/open_the_laptop/open_the_laptop.yaml | planning_failed | 0 |  |
| art/open_the_microwave | art/franka/open_the_microwave/open_the_microwave_part0.yaml | planning_failed | 0 |  |
| art/open_the_microwave_from_scratch | art/split_aloha/open_the_microwave_from_scratch/open_the_microwave_from_scratch.yaml | runtime_error |  | IsADirectoryError(21, 'Is a directory') |
| art/open_the_oven | art/split_aloha/open_the_oven/left/open_the_oven_part0.yaml | planning_failed | 0 |  |
| art/open_the_pot | art/franka/open_the_pot/open_the_pot.yaml | planning_failed | 0 |  |
| art/open_the_trashcan | art/franka/open_the_trashcan/open_the_trashcan.yaml | planning_failed | 0 |  |
| art/pull_the_storagefurniture | art/lift2/pull_the_storagefurniture/left/pull_the_storagefurniture_left_arm_top.yaml | planning_failed | 0 |  |
| art/push_the_storagefurniture | art/lift2/push_the_storagefurniture/left/push_the_storagefurniture_left_arm_top.yaml | planning_failed | 0 |  |
| basic/arrange_the_tableware | basic/lift2/arrange_the_tableware/arrange_the_tableware_part0.yaml | planning_failed | 0 |  |
| basic/conveyor_beef_sandwich | basic/lift2/conveyor_beef_sandwich/conveyor_beef_sandwich.yaml | planning_succeeded | 1209 |  |
| basic/conveyor_ham_sandwich | basic/split_aloha/conveyor_ham_sandwich/conveyor_ham_sandwich.yaml | planning_succeeded | 501 |  |
| basic/hang_the_cup_on_rack | basic/lift2/hang_the_cup_on_rack/left/hang_the_cup_on_rack_part0.yaml | planning_failed | 0 |  |
| basic/insert_the_flower_in_vase | basic/lift2/insert_the_flower_in_vase/left/insert_the_flower_in_vase_part0.yaml | planning_failed | 0 |  |
| basic/insert_the_markpen_in_penholder | basic/lift2/insert_the_markpen_in_penholder/left/insert_the_markpen_in_penholder_part0.yaml | planning_failed | 0 |  |
| basic/pick_the_package_on_conveyor | basic/lift2/pick_the_package_on_conveyor/pick_the_package_on_conveyor.yaml | planning_succeeded | 423 |  |
| basic/pour_Baijiu | basic/lift2/pour_Baijiu/left/pour_Baijiu_left.yaml | planning_failed | 0 |  |
| basic/pour_coke | basic/lift2/pour_coke/pour_half_coke.yaml | planning_failed | 0 |  |
| basic/pour_redwine | basic/lift2/pour_redwine/left/pour_redwine_left.yaml | planning_failed | 0 |  |
| basic/pour_water | basic/split_aloha/pour_water/left/pour_water_left.yaml | runtime_error |  | AttributeError("'Manualpick' object has no attribute 'gripper_cmd'") |
| basic/recovery_pick_objects | basic/lift2/recovery_pick_objects/left/recovery_pick_objects_part0.yaml | runtime_error |  | ValueError('poses in robot frame is not supported: accepted values are [world, body, armbase] only') |
| basic/sort_the_tary_on_rack | basic/lift2/sort_the_tary_on_rack/sort_the_tray_on_rack.yaml | planning_failed | 0 |  |
| basic/sort_the_tray_on_rack | basic/split_aloha/sort_the_tray_on_rack/sort_the_tray_on_rack.yaml | planning_succeeded | 713 |  |
| basic/stack_bowls | basic/lift2/stack_bowls/stack_three_lr.yaml | planning_failed | 0 |  |
| basic/stack_cubes_lift | basic/lift2/stack_cubes_lift/lr.yaml | planning_failed | 0 |  |
| basic/store_the_eggs | basic/genie1/store_the_eggs/lr/098_egg_placer_000_orange.yaml | planning_failed | 0 |  |
| basic/store_the_toothbrushes | basic/lift2/store_the_toothbrushes/store_the_toothbrushes_0.yaml | planning_failed | 0 |  |
| basic/track | basic/franka/track/track_the_targets.yaml | planning_succeeded | 325 |  |
| basic/track_the_targets | basic/lift2/track_the_targets/track_the_targets.yaml | planning_failed | 0 |  |
| basic/water_plant | basic/lift2/water_plant/left/watering_plant_left.yaml | planning_failed | 0 |  |
| example | example/sort_the_rubbish.yaml | planning_succeeded | 670 |  |
| long_horizon/clean_the_dirt_with_brown_cloth | long_horizon/lift2/clean_the_dirt_with_brown_cloth/left/left_dark.yaml | runtime_error |  | ValueError('empty range for randrange() (0, 0, 0)') |
| long_horizon/clean_the_dirt_with_sponge | long_horizon/lift2/clean_the_dirt_with_sponge/left/left_dark.yaml | runtime_error |  | ValueError('empty range for randrange() (0, 0, 0)') |
| long_horizon/clean_the_dirt_with_white_cloth | long_horizon/lift2/clean_the_dirt_with_white_cloth/left/left_dark.yaml | runtime_error |  | ValueError('empty range for randrange() (0, 0, 0)') |
| long_horizon/collaborate_assemble_a_beef_sandwich | long_horizon/lift2/collaborate_assemble_a_beef_sandwich/collaborate_assemble_a_beef_sandwich.yaml | runtime_error |  | KeyError('target_class') |
| long_horizon/collaborate_assemble_a_beef_sandwich_mix | long_horizon/split_aloha/collaborate_assemble_a_beef_sandwich_mix/collaborate_assemble_a_beef_sandwich_mix.yaml | runtime_error |  | KeyError('target_class') |
| long_horizon/collaborate_assemble_a_ham_sandwich | long_horizon/lift2/collaborate_assemble_a_ham_sandwich/collaborate_assemble_a_ham_sandwich.yaml | runtime_error |  | KeyError('target_class') |
| long_horizon/dexpnp | long_horizon/lift2/dexpnp/sort_parts_0.yaml | planning_succeeded | 404 |  |
| long_horizon/flip_package | long_horizon/lift2/flip_package/flip_package_1.yaml | runtime_error |  | AxisError(-1, 0, 'axisb') |
| long_horizon/handover | long_horizon/split_aloha/handover/lr/dish.yaml | planning_failed | 0 |  |
| long_horizon/pack_in_objects | long_horizon/lift2/pack_in_objects/pack_in_objects_part0.yaml | planning_failed | 0 |  |
| long_horizon/pack_out_objects | long_horizon/lift2/pack_out_objects_part0.yaml | planning_failed | 0 |  |
| long_horizon/put_the_trashcan_in_trashcan | long_horizon/franka/put_the_trashcan_in_trashcan_part0.yaml | planning_failed | 0 |  |
| long_horizon/sort_the_rubbish | long_horizon/lift2/sort_the_rubbish/sort_the_rubbish_part0.yaml | planning_succeeded | 598 |  |
| long_horizon/stack_a_beef_sandwich | long_horizon/lift2/stack_a_beef_sandwich/stack_a_beef_sandwich.yaml | planning_failed | 0 |  |
| long_horizon/store_objects_in_the_drawer | long_horizon/lift2/store_objects_in_the_drawer/store_objects_in_the_drawer_2.yaml | planning_failed | 0 |  |
| pick_and_place/dual_pnp | pick_and_place/genie1/dual_pnp/lr/omniobject3d-peach.yaml | planning_failed | 0 |  |
| pick_and_place/single_func_pick | pick_and_place/genie1/single_func_pick/left/phocal-red_wine_glass.yaml | planning_succeeded | 168 |  |
| pick_and_place/single_pick | pick_and_place/franka/single_pick/google_scan-handbag.yaml | planning_succeeded | 145 |  |
| pick_and_place/single_pnp | pick_and_place/genie1/single_pnp/left/google_scan-handbag.yaml | planning_failed | 0 |  |

## 单独重测（不覆盖基线）

| 复测批次 | 任务族 | 状态 | 帧数 | 异常 |
|---|---|---|---:|---|
| arena-textures | long_horizon/clean_the_dirt_with_brown_cloth | planning_failed | 0 |  |
| arena-textures | long_horizon/clean_the_dirt_with_sponge | planning_failed | 0 |  |
| arena-textures | long_horizon/clean_the_dirt_with_white_cloth | planning_failed | 0 |  |
| clean-serial-600 | basic/conveyor_beef_sandwich | planning_succeeded | 1209 |  |
| clean-serial-600 | basic/conveyor_ham_sandwich | planning_succeeded | 501 |  |
| source-fixes | art/heat_the_food_in_the_microwave | planning_failed | 0 |  |
| source-fixes | basic/pour_water | runtime_error |  | NotImplementedError() |
| source-fixes | basic/recovery_pick_objects | planning_failed | 0 |  |
| source-fixes | long_horizon/flip_package | planning_failed | 0 |  |
| texture-pools | long_horizon/clean_the_dirt_with_brown_cloth | runtime_error |  | ValueError('empty range for randrange() (0, 0, 0)') |
| texture-pools | long_horizon/clean_the_dirt_with_sponge | runtime_error |  | ValueError('empty range for randrange() (0, 0, 0)') |
| texture-pools | long_horizon/clean_the_dirt_with_white_cloth | runtime_error |  | ValueError('empty range for randrange() (0, 0, 0)') |

## 能否重建 HF 已发布 episode

抽样读取真实 Parquet，并检查官方 converter：有机器人动作/状态、相机、时间戳，没有完整场景资产与逐帧物体/连杆状态。因此目前能从现有官方任务重新生成配对 episode，不能据此宣称逐条精确复现已发布 HF 视频。需要与源 episode 匹配的原 plan/WorldRecorder、场景及资产。流体、布料和污渍还需要额外非刚体/材质状态缓存。

当前 InternDataEngine 源码尚未找到折衣/毛巾、炉灶旋钮、扫垃圾、识价取物、选饮料、扫码等部分数据集任务的完整对应配置；未证明覆盖全部 70 项。

官方在 [discussion #11](https://huggingface.co/datasets/InternRobotics/InternData-A1/discussions/11) 指向 InternDataEngine 与 [SIM1](https://github.com/InternRobotics/SIM1) 两套生成代码。SIM1 的 Newton/Warp 布料管线不在本次 Isaac Sim 4.1 测试内；这不等于布料代码完全未开源，也不能据此推断已发布 A1 episode 可以逐条精确重放。

运行方式、状态定义和输入约定见 [审计说明](../../work/task-audit/README.md)。全部配置依赖结果见 [all-configs.csv](all-configs.csv)，真实 HF 样本字段见 [actual-parquet-metadata.json](actual-parquet-metadata.json)。

来源：[数据集](https://huggingface.co/datasets/InternRobotics/InternData-A1)、[论文](https://arxiv.org/html/2511.16651v1)、[官方 Quickstart](https://internrobotics.github.io/InternDataEngine-Docs/guides/quickstart.html)。
