"""
device_probe_win.py: Probe device information for Windows
"""
import enum

import re 
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, ClassVar, Optional, Type, Union,List
import sys
import win32api
import win32con
import win32setup
import logging
from ctypes import wintypes
import win32api
import win32con
import ctypes
class SP_DEVINFO_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("ClassGuid", wintypes.GUID),
        ("DevInst", wintypes.DWORD),
        ("Reserved", ctypes.c_void_p),
    ]

# 加载 setupapi.dll
setupapi = ctypes.WinDLL("setupapi")

# 函数原型
SetupDiGetClassDevsW = setupapi.SetupDiGetClassDevsW
SetupDiGetClassDevsW.argtypes = [
    ctypes.POINTER(wintypes.GUID),  # ClassGuid
    wintypes.PWSTR,                  # Enumerator
    wintypes.HWND,                   # hwndParent
    wintypes.DWORD,                   # Flags
]
SetupDiGetClassDevsW.restype = wintypes.HANDLE

SetupDiEnumDeviceInfo = setupapi.SetupDiEnumDeviceInfo
SetupDiEnumDeviceInfo.argtypes = [
    wintypes.HANDLE,                  # DeviceInfoSet
    wintypes.DWORD,                    # MemberIndex
    ctypes.POINTER(SP_DEVINFO_DATA),   # DeviceInfoData
]
SetupDiEnumDeviceInfo.restype = wintypes.BOOL

SetupDiGetDeviceInstanceIdW = setupapi.SetupDiGetDeviceInstanceIdW
SetupDiGetDeviceInstanceIdW.argtypes = [
    wintypes.HANDLE,                  # DeviceInfoSet
    ctypes.POINTER(SP_DEVINFO_DATA),   # DeviceInfoData
    wintypes.PWSTR,                    # DeviceInstanceId
    wintypes.DWORD,                     # DeviceInstanceIdSize
    wintypes.PDWORD,                    # RequiredSize
]
SetupDiGetDeviceInstanceIdW.restype = wintypes.BOOL

SetupDiGetDeviceRegistryPropertyW = setupapi.SetupDiGetDeviceRegistryPropertyW
SetupDiGetDeviceRegistryPropertyW.argtypes = [
    wintypes.HANDLE,                  # DeviceInfoSet
    ctypes.POINTER(SP_DEVINFO_DATA),   # DeviceInfoData
    wintypes.DWORD,                     # Property
    ctypes.POINTER(wintypes.DWORD),     # PropertyRegDataType
    ctypes.POINTER(wintypes.BYTE),      # PropertyBuffer
    wintypes.DWORD,                     # PropertyBufferSize
    wintypes.PDWORD,                    # RequiredSize
]
SetupDiGetDeviceRegistryPropertyW.restype = wintypes.BOOL

SetupDiDestroyDeviceInfoList = setupapi.SetupDiDestroyDeviceInfoList
SetupDiDestroyDeviceInfoList.argtypes = [wintypes.HANDLE]
SetupDiDestroyDeviceInfoList.restype = wintypes.BOOL

# 常量
DIGCF_PRESENT = 0x00000002
SPDRP_DEVICEDESC = 0x00000000
SPDRP_MFG = 0x0000000B
INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value
USB_DEVICE_GUID = "{36fc9e60-c465-11cf-8056-444553540000}"

def guid_from_string(guid_str):
    """将 GUID 字符串转换为 wintypes.GUID 结构"""
    import uuid
    g = uuid.UUID(guid_str)
    return wintypes.GUID(g.time_low, g.time_mid, g.time_hi_version,
                         (g.clock_seq_hi_variant << 8) | g.clock_seq_low,
                         bytes.fromhex(g.hex[-12:]))

USB_GUID = guid_from_string(USB_DEVICE_GUID)

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
            c = wmi.WMI()
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

        return (vendor_id, device_id_val, device_class, device_speed,
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

def usb_device_probe() -> List[USBDevice]:
    """扫描所有 USB 设备（排除集线器），返回 USBDevice 对象列表。"""
    devices = []
    try:
        c = wmi.WMI()
        pnp_devices = c.Win32_PnPEntity(ConfigManagerErrorCode=0)
        for pnp in pnp_devices:
            dev_id = pnp.DeviceID or ''
            if 'VID_' not in dev_id.upper():
                continue

            match = re.search(r'VID_([0-9A-F]{4})&PID_([0-9A-F]{4})', dev_id, re.I)
            if not match:
                continue
            vendor_id = int(match.group(1), 16)
            device_id_val = int(match.group(2), 16)
            product_name = pnp.Name or ''
            vendor_name = pnp.Manufacturer or None

            # 获取设备类和序列号
            device_class = 0
            serial_number = None
            try:
                escaped_id = dev_id.replace('\\', '\\\\')
                usb_devs = c.Win32_USBDevice(DeviceID=escaped_id)
                if usb_devs:
                    usb = usb_devs[0]
                    if hasattr(usb, 'ClassCode') and usb.ClassCode:
                        device_class = int(usb.ClassCode)
                    if hasattr(usb, 'SerialNumber') and usb.SerialNumber:
                        serial_number = usb.SerialNumber
            except Exception:
                pass

            # 跳过集线器（Class 0x09）
            if device_class == 0x09:
                continue

            usb_device = USBDevice(
                vendor_id=vendor_id,
                device_id=device_id_val,
                device_class=device_class,
                device_speed=0,
                product_name=product_name,
                vendor_name=vendor_name,
                serial_number=serial_number
            )
            usb_device.detect()
            devices.append(usb_device)
    except Exception as e:
        print(f"WMI 扫描出错: {e}")
    return devices

# 测试代码
if __name__ == "__main__":
    devs = usb_device_probe()
    print(f"共发现 {len(devs)} 个 USB 设备")
    for d in devs:
        print(f"{d.vendor_name or '未知厂商'} {d.product_name} (VID:{d.vendor_id:04X}, PID:{d.device_id:04X}) 类:{d.device_class}")
        if d.device_class == USBDevice.ClassCode.HID:
            print("  → HID 设备（键盘/鼠标等）")