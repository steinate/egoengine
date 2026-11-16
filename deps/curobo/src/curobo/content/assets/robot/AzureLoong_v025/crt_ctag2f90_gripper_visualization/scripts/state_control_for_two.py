# # -*- coding: UTF-8 -*-
# import minimalmodbus
# import serial
# import threading
# import rospy
# import time
# from collections import deque
# from datetime import datetime
# from sensor_msgs.msg import JointState
# from std_msgs.msg import Float32
# from sdk.msg import RosControl, AlohaCmd, PuppetState, PuppetIMU
# from sdk.srv import GetEnvironment, ManageNode
# from mocap2robot.msg import vp_control

# # 寄存器地址定义
# ENABLE = 0x0100
# POSITION_HIGH_8 = 0x0102
# POSITION_LOW_8 = 0x0103
# SPEED = 0x0104
# FORCE = 0x0105
# ACCELERATION = 0x0106
# DEACCELERATION = 0x0107
# MOTION_TRIGGER = 0x0108
# UPDATE_MODE = 0x010F
# RETURN_ZERO = 0x0402
# POSITION_FEEDBACK_HIGH = 0x0609
# POSITION_FEEDBACK_LOW = 0x060A

# # 夹爪配置
# GRIPPER_CONFIGS = {
#     'left': {
#         'port': '/dev/gripper_left',
#         'address': 1,
#         'baud': 115200
#     },
#     'right': {
#         'port': '/dev/gripper_right',
#         'address': 1,
#         'baud': 115200
#     }
# }

# class GripperController:
#     def __init__(self, port, address, baud):
#         self.instrument = minimalmodbus.Instrument(port, address)
#         self.instrument.serial.baudrate = baud
#         self.instrument.serial.timeout = 0.05
#         self.instrument.serial.writeTimeout = 0.01
#         # 优化串口性能
#         self.instrument.serial.parity = serial.PARITY_NONE
#         self.instrument.serial.stopbits = serial.STOPBITS_ONE
#         self.instrument.serial.bytesize = serial.EIGHTBITS
        
#         self.lock = threading.Lock()
#         self.command_queue = deque(maxlen=3)
#         self.last_position = None
#         self.write_thread_active = True
#         self.write_error_count = 0
        
#         try:
#             self._init_gripper()
#             self._start_write_thread()
#             rospy.loginfo("Gripper initialized with optimized parameters")
#         except Exception as e:
#             rospy.logerr(f"Gripper initialization error: {e}")
    
#     def _init_gripper(self):
#         """初始化夹爪参数"""
#         with self.lock:
#             self.instrument.write_register(ENABLE, 1, functioncode=6)
#             time.sleep(0.02)  # 短暂延时确保使能成功
#             self.instrument.write_register(UPDATE_MODE, 1, functioncode=6)

#             self.instrument.write_register(0x0305, 32555, functioncode=6)
#             # self.instrument.write_register(SPEED, 1000, functioncode=6)
#             self.instrument.write_register(FORCE, 100, functioncode=6)
#             self.instrument.write_register(ACCELERATION, 40000, functioncode=6)
#             self.instrument.write_register(DEACCELERATION, 40000, functioncode=6)
    
#     def _start_write_thread(self):
#         """启动写入线程"""
#         self._write_thread = threading.Thread(target=self._write_loop)
#         self._write_thread.daemon = True
#         self._write_thread.start()
    
#     def _write_loop(self):
#         """优化的写入循环"""
#         while self.write_thread_active:
#             try:
#                 if self.command_queue:
#                     position =  self.command_queue[-1]  # 获取最新命令
#                     self.command_queue.clear()  # 清除旧命令
                    
#                     # 避免重复写入
#                     if position == self.last_position:
#                         continue
                    
#                     # 批量写入
#                     with self.lock:
#                         position_high = (position >> 16) & 0xFFFF
#                         position_low = position & 0xFFFF
                        
#                         print(f"position_high, position_low:{position_high}, {position_low}")
                        
#                         try:
#                             self.instrument.write_registers(
#                                 POSITION_HIGH_8, 
#                                 [position_high, position_low]
#                             )
#                             self.instrument.write_register(MOTION_TRIGGER, 1, functioncode=6)
#                             self.last_position = position
#                             self.write_error_count = 0
#                         except Exception as e:
#                             self.write_error_count += 1
#                             if self.write_error_count >= 3:
#                                 rospy.logerr(f"Multiple write errors: {e}")
#                                 self._reinit_serial()
#                                 self.write_error_count = 0
#                             continue
                
#                 time.sleep(0.002)
#             except Exception as e:
#                 rospy.logerr(f"Write loop error: {e}")
#                 time.sleep(0.1)
    
#     def _reinit_serial(self):
#         """重新初始化串口连接"""
#         try:
#             self.instrument.serial.close()
#             time.sleep(0.1)
#             self.instrument.serial.open()
#             self._init_gripper()
#             rospy.loginfo("Serial connection reinitialized")
#         except Exception as e:
#             rospy.logerr(f"Serial reinit error: {e}")

#     def write_position(self, position):
#         """非阻塞的位置写入"""
#         try:
#             self.command_queue.append(position)
#         except Exception as e:
#             rospy.logerr(f"Queue write error: {e}")

#     def get_position(self):
#         """读取当前位置"""
#         try:
#             with self.lock:
#                 high = self.instrument.read_register(POSITION_FEEDBACK_HIGH, functioncode=3)
#                 low = self.instrument.read_register(POSITION_FEEDBACK_LOW, functioncode=3)
#                 position = float((high << 16) + low)
#                 return position
#         except Exception as e:
#             rospy.logerr(f"Position read error: {e}")
#             return None
    
#     def __del__(self):
#         """清理资源"""
#         self.write_thread_active = False
#         if hasattr(self, '_write_thread'):
#             self._write_thread.join(timeout=1.0)

# class DualGripperNode:
#     def __init__(self):
#         self.grippers = {}
#         self.command_times = {}
#         self.min_interval = 0.01  # 10ms最小间隔
#         self.debug_mode = rospy.get_param('~debug', False)
        
#         # 初始化夹爪
#         for name, config in GRIPPER_CONFIGS.items():
#             try:
#                 gripper = GripperController(config['port'], config['address'], config['baud'])
#                 self.grippers[name] = gripper
#                 self.command_times[name] = time.time()
#                 rospy.loginfo(f"{name} gripper initialized successfully")
#             except Exception as e:
#                 rospy.logerr(f"{name} gripper initialization failed: {e}")

#         # 发布器设置
#         self.position_pubs = {
#             'left': rospy.Publisher('left_gripper_position', Float32, queue_size=1),
#             'right': rospy.Publisher('right_gripper_position', Float32, queue_size=1)
#         }

#         # 启动位置发布线程
#         for name in self.grippers:
#             thread = threading.Thread(target=self.publish_position, args=(name,))
#             thread.daemon = True
#             thread.start()

#     def publish_position(self, gripper_name):
#         """发布位置信息的线程函数"""
#         rate = rospy.Rate(20)  # 20Hz更新频率
#         while not rospy.is_shutdown():
#             try:
#                 position = self.grippers[gripper_name].get_position()
#                 if position is not None:
#                     msg = Float32()
#                     msg.data = position
#                     self.position_pubs[gripper_name].publish(msg)
#             except Exception as e:
#                 rospy.logerr(f"{gripper_name} position publishing error: {e}")
#             rate.sleep()

#     def joint_states_vp_callback(self, data):

#         """优化的VP控制回调函数"""
#         try:
#             current_time = time.time()
            
#             # 快速计算位置
#             left_pos = int((data.vcap[0]/50.0) * 9000)
#             right_pos = int((data.vcap[1]/50.0) * 9000)
            
#             if self.debug_mode:
#                 rospy.logdebug(f"Target positions - Left: {left_pos}, Right: {right_pos}")
            
#             # 更新左夹爪
#             if (current_time - self.command_times['left']) >= self.min_interval:
#                 self.grippers['left'].write_position(left_pos)
#                 self.command_times['left'] = current_time
            
#             # 更新右夹爪
#             if (current_time - self.command_times['right']) >= self.min_interval:
#                 self.grippers['right'].write_position(right_pos)
#                 self.command_times['right'] = current_time
                
#         except Exception as e:
#             rospy.logerr(f"VP callback error: {e}")
    
#     def joint_states_auto_callback(self, data):

#         """优化的VP控制回调函数"""
#         try:
#             current_time = time.time()
            
#             # 快速计算位置
#             left_pos = int((data.position[0]/50.0) * 9000)
#             right_pos = int((data.position[1]/50.0) * 9000)
            
#             if self.debug_mode:
#                 rospy.logdebug(f"Target positions - Left: {left_pos}, Right: {right_pos}")
            
#             # 更新左夹爪
#             if (current_time - self.command_times['left']) >= self.min_interval:
#                 self.grippers['left'].write_position(left_pos)
#                 self.command_times['left'] = current_time
            
#             # 更新右夹爪
#             if (current_time - self.command_times['right']) >= self.min_interval:
#                 self.grippers['right'].write_position(right_pos)
#                 self.command_times['right'] = current_time
                
#         except Exception as e:
#             rospy.logerr(f"VP callback error: {e}")


# def main():
#     rospy.init_node('dual_gripper_control', anonymous=True)
    
#     try:
#         node = DualGripperNode()
#         rospy.loginfo("Dual gripper control node started")
        
#         # 订阅控制命令
#         # rospy.Subscriber("/vp_control", vp_control, node.joint_states_vp_callback, queue_size=1)
#         rospy.Subscriber("/gripper_action_pub", JointState, node.joint_states_auto_callback, queue_size=1)
        
#         rospy.spin()
#     except Exception as e:
#         rospy.logerr(f"Node error: {e}")

# if __name__ == '__main__':
#     main()


# -*- coding: UTF-8 -*-
import minimalmodbus
import serial
import threading
import rospy
import time
from collections import deque
from datetime import datetime
from sensor_msgs.msg import JointState
from std_msgs.msg import Float32, Int32
from perception.msg import RosControl, AlohaCmd, PuppetState, PuppetIMU
from perception.srv import GetEnvironment, ManageNode
from mocap2robot.msg import vp_control

# 寄存器地址定义
ENABLE = 0x0100
POSITION_HIGH_8 = 0x0102
POSITION_LOW_8 = 0x0103
SPEED = 0x0104
FORCE = 0x0105
ACCELERATION = 0x0106
DEACCELERATION = 0x0107
MOTION_TRIGGER = 0x0108
UPDATE_MODE = 0x010F
RETURN_ZERO = 0x0402
POSITION_FEEDBACK_HIGH = 0x0609
POSITION_FEEDBACK_LOW = 0x060A

# 模式定义
MODE_AUTO = 105      # 自主模式
MODE_VP = 104       # VP控制模式
MODE_DEFAULT = 102  # 默认值

# 夹爪配置
GRIPPER_CONFIGS = {
    'left': {
        'port': '/dev/gripper_left',
        #'port': '/dev/ttyUSB0',
        'address': 1,
        'baud': 115200
    },
    'right': {
        'port': '/dev/gripper_right',
        #'port': '/dev/ttyUSB1',
        'address': 1,
        'baud': 115200
    }
}

class GripperController:
    def __init__(self, port, address, baud):
        self.instrument = minimalmodbus.Instrument(port, address)
        self.instrument.serial.baudrate = baud
        self.instrument.serial.timeout = 0.05
        self.instrument.serial.writeTimeout = 0.01
        # 优化串口性能
        self.instrument.serial.parity = serial.PARITY_NONE
        self.instrument.serial.stopbits = serial.STOPBITS_ONE
        self.instrument.serial.bytesize = serial.EIGHTBITS
        
        self.lock = threading.Lock()
        self.command_queue = deque(maxlen=3)
        self.last_position = None
        self.write_thread_active = True
        self.write_error_count = 0
        
        try:
            self._init_gripper()
            self._start_write_thread()
            rospy.loginfo("Gripper initialized with optimized parameters")
        except Exception as e:
            rospy.logerr(f"Gripper initialization error: {e}")
    
    def _init_gripper(self):
        """初始化夹爪参数"""
        with self.lock:
            self.instrument.write_register(ENABLE, 1, functioncode=6)
            time.sleep(0.02)  # 短暂延时确保使能成功
            self.instrument.write_register(UPDATE_MODE, 1, functioncode=6)

            self.instrument.write_register(0x0305, 32555, functioncode=6)
            self.instrument.write_register(FORCE, 100, functioncode=6)
            self.instrument.write_register(ACCELERATION, 40000, functioncode=6)
            self.instrument.write_register(DEACCELERATION, 40000, functioncode=6)
    
    def _start_write_thread(self):
        """启动写入线程"""
        self._write_thread = threading.Thread(target=self._write_loop)
        self._write_thread.daemon = True
        self._write_thread.start()
    
    def _write_loop(self):
        """优化的写入循环"""
        while self.write_thread_active:
            try:
                if self.command_queue:
                    position = self.command_queue[-1]  # 获取最新命令
                    self.command_queue.clear()  # 清除旧命令
                    
                    if position == self.last_position:
                        continue
                    
                    with self.lock:
                        position_high = (position >> 16) & 0xFFFF
                        position_low = position & 0xFFFF
                        
                        try:
                            self.instrument.write_registers(
                                POSITION_HIGH_8, 
                                [position_high, position_low]
                            )
                            self.instrument.write_register(MOTION_TRIGGER, 1, functioncode=6)
                            self.last_position = position
                            self.write_error_count = 0
                        except Exception as e:
                            self.write_error_count += 1
                            if self.write_error_count >= 3:
                                rospy.logerr(f"Multiple write errors: {e}")
                                self._reinit_serial()
                                self.write_error_count = 0
                            continue
                
                time.sleep(0.002)
            except Exception as e:
                rospy.logerr(f"Write loop error: {e}")
                time.sleep(0.1)
    
    def _reinit_serial(self):
        """重新初始化串口连接"""
        try:
            self.instrument.serial.close()
            time.sleep(0.1)
            self.instrument.serial.open()
            self._init_gripper()
            rospy.loginfo("Serial connection reinitialized")
        except Exception as e:
            rospy.logerr(f"Serial reinit error: {e}")

    def write_position(self, position):
        """非阻塞的位置写入"""
        try:
            self.command_queue.append(position)
        except Exception as e:
            rospy.logerr(f"Queue write error: {e}")

    def get_position(self):
        """读取当前位置"""
        try:
            with self.lock:
                high = self.instrument.read_register(POSITION_FEEDBACK_HIGH, functioncode=3)
                low = self.instrument.read_register(POSITION_FEEDBACK_LOW, functioncode=3)
                position = float((high << 16) + low)
                return position
        except Exception as e:
            rospy.logerr(f"Position read error: {e}")
            return None
    
    def __del__(self):
        """清理资源"""
        self.write_thread_active = False
        if hasattr(self, '_write_thread'):
            self._write_thread.join(timeout=1.0)

class DualGripperNode:
    def __init__(self):
        self.grippers = {}
        self.command_times = {}
        self.min_interval = 0.01  # 10ms最小间隔
        self.debug_mode = rospy.get_param('~debug', False)
        
        # 控制模式设置
        self.control_mode = "auto"  # 默认为自主控制模式
        self.last_mode_value = MODE_DEFAULT
        self.mode_switch_threshold = rospy.get_param('~mode_switch_threshold', 0.1)  # 模式检测阈值时间
        self.last_mode_change_time = time.time()
        
        # 初始化夹爪
        for name, config in GRIPPER_CONFIGS.items():
            try:
                gripper = GripperController(config['port'], config['address'], config['baud'])
                self.grippers[name] = gripper
                self.command_times[name] = time.time()
                rospy.loginfo(f"{name} gripper initialized successfully")
            except Exception as e:
                rospy.logerr(f"{name} gripper initialization failed: {e}")

        # 发布器设置
        self.position_pubs = {
            'left': rospy.Publisher('left_gripper_position', Float32, queue_size=1),
            'right': rospy.Publisher('right_gripper_position', Float32, queue_size=1)
        }

        # 初始化订阅器
        self.init_subscribers()

        # 启动位置发布线程
        for name in self.grippers:
            thread = threading.Thread(target=self.publish_position, args=(name,))
            thread.daemon = True
            thread.start()

        rospy.loginfo("启动夹爪控制节点，等待模式指令...")
        rospy.loginfo("当前控制模式: %s", self.control_mode)

    def init_subscribers(self):
        """初始化订阅器"""
        # 模式监控订阅器
        self.mode_sub = rospy.Subscriber(
            "/mode", 
            Int32, 
            self.mode_callback, 
            queue_size=1
        )
        
        # VP控制模式订阅器
        self.vp_sub = rospy.Subscriber(
            "/vp_control", 
            vp_control, 
            self.joint_states_vp_callback, 
            queue_size=1
        )
        
        # 自主控制模式订阅器
        self.auto_sub = rospy.Subscriber(
            "/gripper_action_pub", 
            JointState, 
            self.joint_states_auto_callback, 
            queue_size=1
        )

    def mode_callback(self, msg):
        """处理模式值变化"""
        current_time = time.time()
        mode_value = msg.data
        
        # 检查是否是新的模式值
        if mode_value != self.last_mode_value:
            self.last_mode_value = mode_value
            
            # 处理模式切换逻辑
            if mode_value == MODE_AUTO:  # 105
                if self.control_mode != "auto":
                    self.control_mode = "auto"
                    rospy.loginfo("切换到自主控制模式")
                self.last_mode_change_time = current_time
                
            elif mode_value == MODE_VP:  # 104
                if self.control_mode != "vp":
                    self.control_mode = "vp"
                    rospy.loginfo("切换到VP控制模式")
                self.last_mode_change_time = current_time
                
            elif mode_value == MODE_DEFAULT:  # 102
                # 如果超过阈值时间，保持当前模式
                if (current_time - self.last_mode_change_time) > self.mode_switch_threshold:
                    rospy.logdebug("保持当前模式: %s", self.control_mode)

    def publish_position(self, gripper_name):
        """发布位置信息的线程函数"""
        rate = rospy.Rate(20)  # 20Hz更新频率
        while not rospy.is_shutdown():
            try:
                position = self.grippers[gripper_name].get_position()
                if position is not None:
                    msg = Float32()
                    msg.data = position
                    self.position_pubs[gripper_name].publish(msg)
            except Exception as e:
                rospy.logerr(f"{gripper_name} position publishing error: {e}")
            rate.sleep()

    def joint_states_vp_callback(self, data):
        """VP控制回调函数"""
        if self.control_mode != "vp":
            return
            
        try:
            current_time = time.time()
            
            # 计算位置
            left_pos = int((data.vcap[0]/50.0) * 9000)
            right_pos = int((data.vcap[1]/50.0) * 9000)
            
            if self.debug_mode:
                rospy.logdebug(f"VP mode - Target positions - Left: {left_pos}, Right: {right_pos}")
            
            # 更新夹爪位置
            self._update_gripper_positions(left_pos, right_pos, current_time)
                
        except Exception as e:
            rospy.logerr(f"VP callback error: {e}")
    
    def joint_states_auto_callback(self, data):
        """自主控制回调函数"""
        if self.control_mode != "auto":
            return
            
        try:
            current_time = time.time()
            
            # 计算位置
            left_pos = int((data.position[0]/50.0) * 9000)
            right_pos = int((data.position[1]/50.0) * 9000)
            
            if self.debug_mode:
                rospy.logdebug(f"Auto mode - Target positions - Left: {left_pos}, Right: {right_pos}")
            
            # 更新夹爪位置
            self._update_gripper_positions(left_pos, right_pos, current_time)
                
        except Exception as e:
            rospy.logerr(f"Auto callback error: {e}")

    def _update_gripper_positions(self, left_pos, right_pos, current_time):
        """更新夹爪位置的通用方法"""
        # 更新左夹爪
        if (current_time - self.command_times['left']) >= self.min_interval:
            self.grippers['left'].write_position(left_pos)
            self.command_times['left'] = current_time
        
        # 更新右夹爪
        if (current_time - self.command_times['right']) >= self.min_interval:
            self.grippers['right'].write_position(right_pos)
            self.command_times['right'] = current_time

def main():
    rospy.init_node('dual_gripper_control', anonymous=True)
    
    try:
        node = DualGripperNode()
        rospy.loginfo("Dual gripper control node started")
        rospy.spin()
    except Exception as e:
        rospy.logerr(f"Node error: {e}")

if __name__ == '__main__':
    main()


# sudo modprobe ftdi_sio
# sudo usermod -a -G dialout $USER
# sudo chmod 666 /dev/gripper_*


# roscore
# roslaunch realsense2_camera multi-camera.launch
# rosrun perception udp_ros_node
# rosrun perception perception_node 
# rosrun mocap2robot vr_mocap_project_quest3_controller_node.py
# python3 /home/enpht/perception_ros1/src/crt_ctag2f90_gripper_visualization/scripts/gripper_upsample.py 
# python3 /home/enpht/perception_ros1/src/crt_ctag2f90_gripper_visualization/scripts/state_control_for_two.py 
