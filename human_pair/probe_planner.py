import sys,json
from pathlib import Path
root=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(root/'runtime41/extscache/omni.warp.core-1.2.1'))
import numpy as np
import torch
from curobo.types.base import TensorDeviceType
from curobo.types.math import Pose
from curobo.types.robot import JointState
from curobo.geom.types import WorldConfig
from curobo.wrap.reacher.motion_gen import MotionGen,MotionGenConfig,MotionGenPlanConfig
from curobo.util_file import load_yaml
ta=TensorDeviceType()
cfg=load_yaml(str(root/'assets/InternDataAssets/curobo/src/curobo/content/configs/robot/fr3_left_arm.yml'))['robot_cfg']
mg=MotionGen(MotionGenConfig.load_from_robot_config(cfg,WorldConfig(),ta,use_cuda_graph=True,
    self_collision_check=True,num_trajopt_seeds=12,num_graph_seeds=12,collision_activation_distance=.03,
    collision_cache={'obb':1000,'mesh':1000},interpolation_dt=.01,project_pose_to_goal_frame=False))
mg.warmup(enable_graph=True,warmup_js_trajopt=False)
q=ta.to_device([[0,-.143,0,-2.435,0,2.235,.789]])
js=JointState.from_position(q,joint_names=mg.kinematics.joint_names)
rows=[]
for x,z in [(.3,.15),(.4,.15),(.5,.15),(.5,.25),(.4,.25)]:
    goal=Pose.from_list([x,.1,z,0,1,0,0],ta)
    ik=mg.ik_solver.solve_single(goal)
    r=mg.plan_single(js,goal,MotionGenPlanConfig(max_attempts=2))
    row={'x':x,'z':z,'ik_success':bool(ik.success.any()),'plan_success':bool(r.success.any()),'status':str(r.status),
         'ik_pos_error':ik.position_error.detach().cpu().tolist(),'ik_rot_error':ik.rotation_error.detach().cpu().tolist()}
    print('PROBE',json.dumps(row),flush=True);rows.append(row)
(root/'outputs41/planner-probe.json').write_text(json.dumps(rows,indent=2))
