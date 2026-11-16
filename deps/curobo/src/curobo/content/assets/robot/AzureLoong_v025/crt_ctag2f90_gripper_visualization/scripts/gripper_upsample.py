#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import rospy
from std_msgs.msg import Float32
from sensor_msgs.msg import JointState
from mocap2robot.msg import vp_control

class GripperPositionRepublisher:
    def __init__(self):
        rospy.init_node('gripper_position_republisher', anonymous=True)
        
        # 参数设置
        self.target_freq = 200.0  # 目标频率
        self.publish_rate = rospy.Rate(self.target_freq)
        
        # 存储最新值
        self.latest_value1 = 0.0
        self.latest_value2 = 0.0
        self.latest_vcap1 = 0.0
        self.latest_vcap2 = 0.0
        self.has_received1 = False
        self.has_received2 = False
        self.has_received_vcap = False
        
        # 订阅者
        self.sub1 = rospy.Subscriber('/left_gripper_position', Float32, self.callback1)
        self.sub2 = rospy.Subscriber('/right_gripper_position', Float32, self.callback2)
        self.sub_vcap = rospy.Subscriber('/vp_control', vp_control, self.vcap_callback)
        
        # 发布者
        self.pub1 = rospy.Publisher('/gripper1_position_mm_upsample', JointState, queue_size=10)
        self.pub2 = rospy.Publisher('/gripper2_position_mm_upsample', JointState, queue_size=10)
        self.pub_action = rospy.Publisher('/gripper_action', JointState, queue_size=10)
    
    def callback1(self, msg):
        self.latest_value1 = msg.data
        self.has_received1 = True
    
    def callback2(self, msg):
        self.latest_value2 = msg.data
        self.has_received2 = True
    
    def vcap_callback(self, msg):
        # 直接使用原始值
        self.latest_vcap1 = msg.vcap[0]
        self.latest_vcap2 = msg.vcap[1]
        self.has_received_vcap = True
        
        # 发布gripper_action
        action_msg = JointState()
        action_msg.header.stamp = rospy.Time.now()
        action_msg.name = ['left_gripper_joint', 'right_gripper_joint']
        action_msg.position = [self.latest_vcap1, self.latest_vcap2]
        action_msg.velocity = []
        action_msg.effort = []
        self.pub_action.publish(action_msg)
    
    def run(self):
        while not rospy.is_shutdown():
            current_time = rospy.Time.now()
            
            # 发布左夹爪位置
            if self.has_received1:
                msg1 = JointState()
                msg1.header.stamp = current_time
                msg1.name = ['left_gripper']
                msg1.position = [self.latest_value1]
                msg1.velocity = []
                msg1.effort = []
                self.pub1.publish(msg1)
            
            # 发布右夹爪位置
            if self.has_received2:
                msg2 = JointState()
                msg2.header.stamp = current_time
                msg2.name = ['right_gripper']
                msg2.position = [self.latest_value2]
                msg2.velocity = []
                msg2.effort = []
                self.pub2.publish(msg2)
            
            self.publish_rate.sleep()

if __name__ == '__main__':
    try:
        republisher = GripperPositionRepublisher()
        rospy.loginfo("夹爪位置重发布节点已启动")
        republisher.run()
    except rospy.ROSInterruptException:
        pass