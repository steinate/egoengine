#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import sys
import os

# 在导入PyQt5之前设置环境变量
os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = '/usr/lib/x86_64-linux-gnu/qt5/plugins'


import sys
import rospy
from sensor_msgs.msg import JointState
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                           QHBoxLayout, QPushButton, QLabel, QSlider, QGroupBox)
from PyQt5.QtCore import Qt, QTimer

class GripperControlGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initROS()
        self.initUI()
        
        # 创建定时器用于更新GUI
        self.timer = QTimer()
        self.timer.timeout.connect(self.publish_state)
        self.timer.start(100)  # 10Hz更新频率

    def initROS(self):
        # ROS初始化
        rospy.init_node('gripper_control_gui', anonymous=True)
        self.pub = rospy.Publisher('/joint_states', JointState, queue_size=10)
        
        # 创建JointState消息
        self.msg = JointState()
        self.msg.name = ['joint1', 'joint2', 'joint3', 'joint4']
        self.msg.position = [0.0, 0.0, 0.0, 0.0]
        self.msg.velocity = []
        self.msg.effort = []

    def initUI(self):
        self.setWindowTitle('双夹爪控制面板')
        self.setGeometry(100, 100, 800, 400)

        # 创建中央部件和主布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # 创建左右夹爪控制组
        left_group = self.create_gripper_group("左夹爪控制", 2)
        right_group = self.create_gripper_group("右夹爪控制", 3)

        # 添加到主布局
        main_layout.addWidget(left_group)
        main_layout.addWidget(right_group)

        # 添加同步控制组
        sync_group = self.create_sync_control()
        main_layout.addWidget(sync_group)

    def create_gripper_group(self, title, joint_index):
        group = QGroupBox(title)
        layout = QVBoxLayout()

        # 创建滑块
        slider = QSlider(Qt.Horizontal)
        slider.setMinimum(0)
        slider.setMaximum(100)
        slider.setValue(0)
        slider.setTickPosition(QSlider.TicksBelow)
        slider.setTickInterval(10)
        
        # 创建标签显示当前值
        value_label = QLabel('位置: 0%')
        
        # 创建开合按钮
        open_btn = QPushButton('完全打开')
        close_btn = QPushButton('完全关闭')

        # 连接信号
        slider.valueChanged.connect(
            lambda value, l=value_label, j=joint_index: self.on_slider_changed(value, l, j))
        open_btn.clicked.connect(
            lambda _, s=slider, j=joint_index: self.on_full_open(s, j))
        close_btn.clicked.connect(
            lambda _, s=slider, j=joint_index: self.on_full_close(s, j))

        # 添加到布局
        layout.addWidget(value_label)
        layout.addWidget(slider)
        
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(open_btn)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        group.setLayout(layout)
        return group

    def create_sync_control(self):
        group = QGroupBox("同步控制")
        layout = QVBoxLayout()

        # 同步开合按钮
        sync_open_btn = QPushButton('同时打开两个夹爪')
        sync_close_btn = QPushButton('同时关闭两个夹爪')
        
        # 添加交替运动按钮
        alternate_btn = QPushButton('开始交替运动')
        self.is_alternating = False
        
        # 连接信号
        sync_open_btn.clicked.connect(self.on_sync_open)
        sync_close_btn.clicked.connect(self.on_sync_close)
        alternate_btn.clicked.connect(self.on_alternate)

        layout.addWidget(sync_open_btn)
        layout.addWidget(sync_close_btn)
        layout.addWidget(alternate_btn)
        
        group.setLayout(layout)
        return group

    def on_slider_changed(self, value, label, joint_index):
        label.setText(f'位置: {value}%')
        # 将0-100的值映射到0-1
        self.msg.position[joint_index] = value / 100.0

    def on_full_open(self, slider, joint_index):
        slider.setValue(100)
        self.msg.position[joint_index] = 1.0

    def on_full_close(self, slider, joint_index):
        slider.setValue(0)
        self.msg.position[joint_index] = 0.0

    def on_sync_open(self):
        self.msg.position[2] = 1.0  # 左夹爪
        self.msg.position[3] = 1.0  # 右夹爪
        # 更新所有滑块
        for slider in self.findChildren(QSlider):
            slider.setValue(100)

    def on_sync_close(self):
        self.msg.position[2] = 0.0
        self.msg.position[3] = 0.0
        # 更新所有滑块
        for slider in self.findChildren(QSlider):
            slider.setValue(0)

    def on_alternate(self):
        self.is_alternating = not self.is_alternating
        sender = self.sender()
        if self.is_alternating:
            sender.setText('停止交替运动')
            self.alternate_state = True
            self.start_alternating()
        else:
            sender.setText('开始交替运动')

    def start_alternating(self):
        if not self.is_alternating:
            return
        
        # 交替开合状态
        if self.alternate_state:
            self.msg.position[2] = 1.0  # 左开
            self.msg.position[3] = 0.0  # 右关
        else:
            self.msg.position[2] = 0.0  # 左关
            self.msg.position[3] = 1.0  # 右开
            
        self.alternate_state = not self.alternate_state
        
        # 更新滑块位置
        sliders = self.findChildren(QSlider)
        sliders[0].setValue(int(self.msg.position[2] * 100))
        sliders[1].setValue(int(self.msg.position[3] * 100))
        
        # 设置下一次交替
        if self.is_alternating:
            QTimer.singleShot(1000, self.start_alternating)

    def publish_state(self):
        """定期发布夹爪状态"""
        try:
            self.msg.header.stamp = rospy.Time.now()
            self.pub.publish(self.msg)
        except Exception as e:
            rospy.logerr(f"发布状态时出错: {e}")

def main():
    app = QApplication(sys.argv)
    gui = GripperControlGUI()
    gui.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    try:
        main()
    except rospy.ROSInterruptException:
        pass