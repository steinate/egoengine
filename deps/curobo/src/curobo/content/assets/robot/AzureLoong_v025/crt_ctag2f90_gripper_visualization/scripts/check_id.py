#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import minimalmodbus
import serial
import time

# 已知的寄存器地址
REGISTERS = {
    0x0100: "ENABLE",
    0x0102: "POSITION_HIGH_8",
    0x0103: "POSITION_LOW_8",
    0x0104: "SPEED",
    0x0105: "FORCE",
    0x0106: "ACCELERATION",
    0x0107: "DEACCELERATION",
    0x0108: "MOTION_TRIGGER",
    0x0402: "RETURN_ZERO",
    0x0609: "POSITION_FEEDBACK_HIGH",
    0x060A: "POSITION_FEEDBACK_LOW"
}

def scan_registers(port='/dev/ttyUSB0', slave_address=1):
    """扫描夹爪的已知寄存器"""
    try:
        # 初始化Modbus通信
        instrument = minimalmodbus.Instrument(port, slave_address)
        instrument.serial.baudrate = 115200
        instrument.serial.timeout = 1

        print(f"\n扫描设备 {port} 的寄存器...")
        print("-" * 50)
        print(f"{'地址':^10} {'名称':<20} {'值':^10} {'十六进制':^10}")
        print("-" * 50)
        
        # 扫描已知的寄存器地址
        for address, name in REGISTERS.items():
            try:
                value = instrument.read_register(address, functioncode=3)
                print(f"0x{address:04X} {name:<20} {value:^10} 0x{value:04X}")
                time.sleep(0.1)  # 避免发送太快
            except Exception as e:
                print(f"0x{address:04X} {name:<20} {'读取失败':^10} {str(e)}")

    except Exception as e:
        print(f"连接设备失败: {e}")

def scan_all_devices():
    """扫描所有USB设备"""
    import glob
    
    # 查找所有USB串口设备
    ports = glob.glob('/dev/ttyUSB*')
    
    if not ports:
        print("未找到USB设备")
        return
        
    print(f"找到以下USB设备: {ports}")
    
    # 扫描每个设备
    for port in ports:
        scan_registers(port)

if __name__ == '__main__':
    print("夹爪寄存器读取工具")
    print("1. 扫描单个设备")
    print("2. 扫描所有USB设备")
    
    choice = input("请选择（1或2）: ")
    
    if choice == '1':
        port = input("请输入设备端口（例如 /dev/ttyUSB0）: ")
        scan_registers(port)
    elif choice == '2':
        scan_all_devices()
    else:
        print("无效的选择")