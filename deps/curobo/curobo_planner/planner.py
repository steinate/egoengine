import time
import os
import torch
import pickle
import quaternion
import numpy as np

from curobo.cuda_robot_model.cuda_robot_model import CudaRobotModel
from curobo.geom.sdf.world import CollisionCheckerType
from curobo.geom.types import Cuboid, WorldConfig
from curobo.geom.sphere_fit import SphereFitType
from curobo.types.base import TensorDeviceType
from curobo.types.camera import CameraObservation
from curobo.types.math import Pose
from curobo.types.robot import JointState, RobotConfig
from curobo.types.state import JointState
from curobo.util_file import get_robot_configs_path, get_world_configs_path, join_path, load_yaml
from curobo.wrap.model.robot_world import RobotWorld, RobotWorldConfig
from curobo.wrap.reacher.motion_gen import MotionGen, MotionGenConfig, MotionGenPlanConfig
from curobo.wrap.reacher.ik_solver import IKSolver, IKSolverConfig
from curobo.wrap.model.robot_segmenter import RobotSegmenter



class FormatPose:
    def __init__(self):
        self.tensor_args = TensorDeviceType()

    def from_transforma_mat(self, transformation_mat):
        q = quaternion.from_rotation_matrix(transformation_mat[:3,:3])
        q_arr = np.array([q.w, q.x, q.y, q.z])
        # q_arr = np.array([q.x, q.y, q.z, q.w])

        tran = transformation_mat[:3,3]

        pose = Pose(position=self.tensor_args.to_device(tran),
                    quaternion=self.tensor_args.to_device(q_arr)
                    )
        return pose

    def from_quat(self, pos, quat):
        pose = Pose(position=self.tensor_args.to_device(pos),
                    quaternion=self.tensor_args.to_device(quat)
                    )
        return pose

format_pose = FormatPose()


class Planner:    
    def __init__(self, 
                 robot, 
                 collision_cfg='./collision.yml'
                 ):
        self.tensor_args = TensorDeviceType()
        self.robot_file = join_path(get_robot_configs_path(), robot)
        # import ipdb;ipdb.set_trace()
        self._load_robot()
        self._load_world(collision_cfg)
        self._init_motion_gen()
        self._init_ik_solver()
        self._init_robot_segmenter()
        

    ''' 加载robot配置文件 '''
    def _load_robot(self):
        self.robot_cfg = load_yaml(self.robot_file)["robot_cfg"]
        
    ''' 实例化collistion world '''
    def _load_world(self, obstacles_cfg):
        self.world_cfg = WorldConfig.from_dict(
            {
                "blox": {
                    "world": {
                        "pose": [0, 0, 0, 1, 0, 0, 0],
                        "integrator_type": "tsdf",
                        "voxel_size": 0.01,
                    }
                }
            }
        )
        # add obstacle into collision_world
        self.world_cfg_obs = WorldConfig.from_dict(load_yaml(obstacles_cfg))
        for obs in self.world_cfg_obs.cuboid:
            self.world_cfg.add_obstacle(obs)
  
    def _init_ik_solver(self):
        ik_config = IKSolverConfig.load_from_robot_config(
            self.robot_cfg,
            None,
            rotation_threshold=0.05,
            position_threshold=0.005,
            num_seeds=20,
            self_collision_check=False,
            self_collision_opt=False,
            tensor_args=self.tensor_args,
            use_cuda_graph=True,
        )
        self.ik_solver = IKSolver(ik_config)

    def _init_robot_segmenter(self):
        self.robot_segmenter = RobotSegmenter.from_robot_file(
            self.robot_file, collision_sphere_buffer=0.01, distance_threshold=0.05, use_cuda_graph=True
        )
 
    ''' 实例化 Motion Planner '''
    def _init_motion_gen(self):
        self.plan_config = MotionGenPlanConfig(
            enable_graph=False, enable_graph_attempt=7, max_attempts=5, enable_finetune_trajopt=True
        )

        motion_gen_config = MotionGenConfig.load_from_robot_config(
            self.robot_cfg,
            self.world_cfg,
            self.tensor_args,
            trajopt_tsteps=32,
            collision_checker_type=CollisionCheckerType.BLOX,
            use_cuda_graph=True,
            num_trajopt_seeds=32,
            num_graph_seeds=24,
            interpolation_dt=0.03,  # 0.03
            collision_activation_distance=0.025,    # 0.025
            acceleration_scale=1.0,
            self_collision_check=False,      # 容易自锁========
            maximum_trajectory_dt=0.25, # 0.25
            finetune_dt_scale=1.05, # 1.05
            fixed_iters_trajopt=True,
            finetune_trajopt_iters=300,
            minimize_jerk=True,
        )
        self.motion_gen = MotionGen(motion_gen_config)
        # import ipdb;ipdb.set_trace()
        print("warming up..")
        self.motion_gen.warmup(warmup_js_trajopt=False)
        
        self.world_model = self.motion_gen.world_collision

    ''' attach被抓物体至ee link '''
    def attach_target(self, 
                      attach_pose,
                      attach_obj,
                      sphere_fit_type = SphereFitType.VOXEL_VOLUME_SAMPLE_SURFACE,
                      surface_sphere_radius = 0.001,
                      voxelize_method = 'ray',
                      remove_obstacles_from_world_config = False,
                      n_spheres=6,
                      link_name = "attached_object",
                      ):
        
        
        pos, quater = attach_pose
        # pos = np.array([-0.61692637, -0.06009333,  0.52288121])
        # quater = np.array([-0.73811456, -0.21932792,  0.60144261,  0.21295291])

        ee_pose = Pose(
            position=self.tensor_args.to_device(pos),
            quaternion=self.tensor_args.to_device(quater),
        )
        
        # 作用还未知
        world_objects_pose_offset = Pose.from_list([0, 0, 0.002, 1, 0, 0, 0], self.tensor_args)
        if world_objects_pose_offset is not None:
            ee_pose = world_objects_pose_offset.inverse().multiply(ee_pose)

        obs = Cuboid(
                name='target_obj',
                pose = [pos[0], pos[1], pos[2]+0.23, 1, 0, 0, 0],
                dims = [0.1, 0.1, 1],
            )
        sph = obs.get_bounding_spheres(
            n_spheres,
            surface_sphere_radius,
            pre_transform_pose=ee_pose,
            tensor_args=self.tensor_args,
            fit_type=sphere_fit_type,
            voxelize_method=voxelize_method,
        )
        sph_list = [s.position + [s.radius] for s in sph]


        spheres = self.tensor_args.to_device(torch.as_tensor(sph_list))

        max_spheres = self.motion_gen.robot_cfg.kinematics.kinematics_config.get_number_of_spheres(link_name)
        if spheres.shape[0] > max_spheres:
            spheres = spheres[: spheres.shape[0]]
        
        # sphere_tensor = torch.zeros((max_spheres, 4))
        # sphere_tensor[:, 3] = -10.0
        # sphere_tensor[: spheres.shape[0], :] = spheres.contiguous()



        sphere_tensor = torch.zeros((3, 4))
        sphere_tensor[:,3] = 0.03   # radius
        sphere_tensor[:,2] = 0.25   # Z

        sphere_tensor[0,1] = attach_obj[0]-0.06 # 0.03   # Y(向上)
        sphere_tensor[1,1] = 0.0
        sphere_tensor[2,1] = attach_obj[1]+0.06 # -0.03


        # import ipdb;ipdb;ipdb.set_trace()
        print(attach_obj)
        print(spheres.shape)
        self.motion_gen.attach_spheres_to_robot(sphere_tensor=sphere_tensor, link_name=link_name)

    ''' 更新collision world (RGB-D) '''
    def update_rgbd(self, observation, joint_position=None, save_mesh=None):
        self.world_model.decay_layer("world")
        
        
        depth = torch.Tensor(observation['depth']).to(self.tensor_args.device)#.unsqueeze(0) * 1000
        intrinsics = torch.Tensor(observation['cam_info']['K'])
        camera_pose = torch.Tensor(observation['c2w'])


        # self.world_model.clear_blox_layer('world')
        # Update RGB-D data into NVBlox and compute colision
        data_camera = CameraObservation(
                depth_image=depth, intrinsics=intrinsics, pose=format_pose.from_transforma_mat(camera_pose)
            )
        data_camera = data_camera.to(device=self.tensor_args.device)
        
    
        self.world_model.add_camera_frame(data_camera, "world")
        self.world_model.process_camera_frames("world", False)
        torch.cuda.synchronize()
        self.world_model.update_blox_hashes()

     

        if save_mesh is not None:
            coll_mesh = self.motion_gen.world_coll_checker.get_mesh_in_bounding_box(
                            Cuboid(name="test", pose=[0, 0, 0, 1, 0, 0, 0], dims=[2, 2, 2]),
                            voxel_size=0.005,
                        )
            coll_mesh.save_as_mesh(save_mesh)
    
    def solve_ik(self, target_pose, type='AvoidObs'):
        # import ipdb;ipdb.set_trace()
        if type == 'AvoidObs':
            ik_goal = format_pose.from_transforma_mat(target_pose)
            result = self.motion_gen.solve_ik(ik_goal)
        elif type == 'Simple':
            ik_goal = format_pose.from_transforma_mat(target_pose)
            result = self.ik_solver.solve_batch(ik_goal)
        else:
            raise NotImplementedError
        torch.cuda.synchronize()
        return result.success.item(), result.js_solution.position.cpu().numpy()[0,0]
        
    ''' Plan trajectory '''
    def plan(self, 
            joint_pos, 
            target_pose,
            attach_pose=None,
            attach_obj=None,
            ):
        ''' 
        Args:
            joint_pos: 当前关节位置      List
            target_pose: 目标位姿       np.ndarray, 4x4 matrix
        
        Return:
            cmd_plan: 规划的关节轨迹(joint pos trajectory)  np.ndarray
        
        '''
        # Motion Plan with current state and target pose
        joint_state = JointState(
                position=self.tensor_args.to_device(joint_pos),
                velocity=self.tensor_args.to_device(np.zeros_like(joint_pos)),
                acceleration=self.tensor_args.to_device(np.zeros_like(joint_pos)),
                jerk=self.tensor_args.to_device(np.zeros_like(joint_pos)),
                joint_names=self.motion_gen.kinematics.joint_names,
            )
        
        joint_state = joint_state.get_ordered_joint_state(
            self.motion_gen.kinematics.joint_names
            )
        
        
        
        ik_goal = format_pose.from_transforma_mat(target_pose)
        
        
        
        if attach_obj is not None:
            self.attach_target(attach_pose, attach_obj)
            
        # Planning
        result = self.motion_gen.plan_single(joint_state.unsqueeze(0), ik_goal, self.plan_config)
        succ = result.success.item() 

        # Plan Results
        cmd_plan = None
        if succ or (result.position_error is not None and result.position_error.item()<=0.005):
            cmd_plan = result.get_interpolated_plan()
            cmd_plan = self.motion_gen.get_full_js(cmd_plan).position.cpu()
        return cmd_plan
            
    def forward_kinematics(self, joint_pos):
        fk = self.motion_gen.kinematics.forward(joint_pos)
        return fk
    
    
if __name__=='__main__':
    current_joint_position = np.array([-0.17328421673230957, 0.020776281232103483, 0.2789527477358542, -1.271056110059985, 0.009799507124556435, 1.2879484589971408, -0.7048105101618843])
    target_ee_pose = np.array([
        [    0.79962,   -0.083815,     0.59462,     0.21639],
        [  -0.027938,    -0.99432,    -0.10259,  -0.0055979],
        [    0.59985,    0.065419,    -0.79743,     0.60838],
        [          0,           0,           0,           1]]
    )

    motion_planner = Planner('franka.yml', 'collision.yml')
    trajectory = motion_planner.plan(current_joint_position, target_ee_pose)
    
    if trajectory is not None:
        print(trajectory)
    else:
        print("Failed to plan trajectory")



    

