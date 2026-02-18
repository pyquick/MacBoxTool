"""
device_probe_win.py: Probe device information for Windows
"""
import enum
import itertools
import subprocess
import plistlib
import hashlib
import re 
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, ClassVar, Optional, Type, Union,List
import sys
import wmi
from ..datasets import (
    pci_data,
    usb_data
)
import logging
from ..support import utilities_win

def class_code_to_bytes(class_code: int) -> bytes:
    return class_code.to_bytes(4, byteorder="little")

@dataclass
class CPU:
    name: str
    flags: list[str]
    leafs: list[str]

@dataclass
class USBDevice:
    vendor_id:     int
    device_id:     int
    device_class:  int
    device_speed:  int
    product_name:  str
    vendor_name:   Optional[str] = None
    serial_number: Optional[str] = None

    @classmethod
    def from_wmi(cls, wmi_device):
        """
        从 WMI 设备对象（Win32_PnPEntity 实例）提取 USB 设备信息。
        返回 (vendor_id, device_id, device_class, device_speed, product_name, vendor_name, serial_number)
        """
        device_id_str = wmi_device.DeviceID or ''
        # 解析 VID 和 PID
        match = re.search(r'VID_([0-9A-F]{4})&PID_([0-9A-F]{4})', device_id_str, re.I)
        if match:
            vendor_id = int(match.group(1), 16)
            device_id_val = int(match.group(2), 16)
        else:
            vendor_id = 0
            device_id_val = 0

        product_name = wmi_device.Name or ''
        vendor_name = wmi_device.Manufacturer or None

        # 尝试从 Win32_USBDevice 获取 ClassCode 和 SerialNumber
        device_class = 0
        serial_number = None
        try:
            c = wmi.WMI()  # 每个设备新建连接（可接受），也可优化为传入已有连接
            # DeviceID 中的反斜杠需要转义
            escaped_id = device_id_str.replace('\\', '\\\\')
            usb_devices = c.Win32_USBDevice(DeviceID=escaped_id)
            if usb_devices:
                usb_dev = usb_devices[0]
                if hasattr(usb_dev, 'ClassCode') and usb_dev.ClassCode is not None:
                    device_class = int(usb_dev.ClassCode)
                if hasattr(usb_dev, 'SerialNumber') and usb_dev.SerialNumber:
                    serial_number = usb_dev.SerialNumber
        except Exception:
            # 查询失败则使用默认值
            pass

        # 设备速度无法从 WMI 直接获取，设为 0
        device_speed = 0

        return cls(vendor_id, device_id_val, device_class, device_speed,
                product_name, vendor_name, serial_number)


    def detect(self):
        self.detect_class()
        self.detect_speed()


    def detect_class(self) -> None:
        for device_class in self.ClassCode:
            if self.device_class == device_class.value:
                self.device_class = device_class


    def detect_speed(self) -> None:
        for speed in self.Speed:
            if self.device_speed == speed.value:
                self.device_speed = speed



    class Speed(enum.Enum):
        LOW_SPEED        = 0x01
        FULL_SPEED       = 0x02
        HIGH_SPEED       = 0x03
        SUPER_SPEED      = 0x04
        SUPER_SPEED_PLUS = 0x05


    class ClassCode(enum.Enum):
        # https://www.usb.org/defined-class-codes
        GENERIC           = 0x00
        AUDIO             = 0x01
        CDC_CONTROL       = 0x02
        HID               = 0x03
        PHYSICAL          = 0x05
        IMAGE             = 0x06
        PRINTER           = 0x07
        MASS_STORAGE      = 0x08
        HUB               = 0x09
        CDC_DATA          = 0x0A
        SMART_CARD        = 0x0B
        CONTENT_SEC       = 0x0D
        VIDEO             = 0x0E
        PERSONAL_HEALTH   = 0x0F
        AUDIO_VIDEO       = 0x10
        BILLBOARD         = 0x11
        USB_TYPE_C_BRIDGE = 0x12
        DISPLAY_BDP       = 0x13
        I3C               = 0x3C
        DIAGNOSTIC        = 0xDC
        WIRELESS          = 0xE0
        MISCELLANEOUS     = 0xEF
        APPLICATION       = 0xFE
        VENDOR_SPEC       = 0xFF