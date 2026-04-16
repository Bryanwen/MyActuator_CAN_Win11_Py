# -*- coding: utf-8 -*-
"""
ZLG USBCAN ctypes 封装（精简版，仅含双电机通讯所需接口）
硬件：USBCAN-I / USBCAN-II，SJA1000 控制器
"""

from ctypes import *
import platform
import os
import sys

# ── 常量 ────────────────────────────────────────────────────────────────────
ZCAN_DEVICE_TYPE      = c_uint
INVALID_DEVICE_HANDLE = 0
INVALID_CHANNEL_HANDLE = 0
ZCAN_STATUS_OK        = 1
ZCAN_TYPE_CAN         = c_uint(0)

# 设备类型号
ZCAN_USBCAN1 = ZCAN_DEVICE_TYPE(3)
ZCAN_USBCAN2 = ZCAN_DEVICE_TYPE(4)

# ── ctypes 数据结构 ─────────────────────────────────────────────────────────

class _ZCAN_CHANNEL_CAN_INIT_CONFIG(Structure):
    _fields_ = [("acc_code", c_uint),
                ("acc_mask", c_uint),
                ("reserved", c_uint),
                ("filter",   c_ubyte),
                ("timing0",  c_ubyte),
                ("timing1",  c_ubyte),
                ("mode",     c_ubyte)]

class _ZCAN_CHANNEL_CANFD_INIT_CONFIG(Structure):
    _fields_ = [("acc_code",    c_uint),
                ("acc_mask",    c_uint),
                ("abit_timing", c_uint),
                ("dbit_timing", c_uint),
                ("brp",         c_uint),
                ("filter",      c_ubyte),
                ("mode",        c_ubyte),
                ("pad",         c_ushort),
                ("reserved",    c_uint)]

class _ZCAN_CHANNEL_INIT_CONFIG(Union):
    _fields_ = [("can",   _ZCAN_CHANNEL_CAN_INIT_CONFIG),
                ("canfd", _ZCAN_CHANNEL_CANFD_INIT_CONFIG)]

class ZCAN_CHANNEL_INIT_CONFIG(Structure):
    _fields_ = [("can_type", c_uint),
                ("config",   _ZCAN_CHANNEL_INIT_CONFIG)]

class ZCAN_CAN_FRAME(Structure):
    _fields_ = [("can_id",  c_uint, 32),
                ("can_dlc", c_ubyte),
                ("_pad",    c_ubyte),
                ("_res0",   c_ubyte),
                ("_res1",   c_ubyte),
                ("data",    c_ubyte * 8)]

class ZCAN_Transmit_Data(Structure):
    _fields_ = [("frame", ZCAN_CAN_FRAME), ("transmit_type", c_uint)]

class ZCAN_Receive_Data(Structure):
    _fields_ = [("frame", ZCAN_CAN_FRAME), ("timestamp", c_ulonglong)]

# ── DLL 路径配置 ─────────────────────────────────────────────────────────────
_KERNEL_DIR = os.path.dirname(os.path.abspath(__file__))
if sys.version_info >= (3, 8):
    os.add_dll_directory(_KERNEL_DIR)

# ── ZCAN 驱动封装类 ──────────────────────────────────────────────────────────

class ZCAN:
    def __init__(self):
        if platform.system() != "Windows":
            raise RuntimeError("仅支持 Windows 系统")
        _dll_path = os.path.join(_KERNEL_DIR, "zlgcan.dll")
        if not os.path.exists(_dll_path):
            raise FileNotFoundError(
                f"找不到 zlgcan.dll：{_dll_path}\n"
                "请将 motor_can_minimal/kerneldlls/ 中的 zlgcan.dll 复制到此目录。"
            )
        self._dll = windll.LoadLibrary(_dll_path)

    def OpenDevice(self, device_type, device_index, reserved):
        return self._dll.ZCAN_OpenDevice(device_type, device_index, reserved)

    def CloseDevice(self, handle):
        return self._dll.ZCAN_CloseDevice(handle)

    def InitCAN(self, dev_handle, chn_index, init_config):
        return self._dll.ZCAN_InitCAN(dev_handle, chn_index, byref(init_config))

    def StartCAN(self, chn_handle):
        return self._dll.ZCAN_StartCAN(chn_handle)

    def ResetCAN(self, chn_handle):
        return self._dll.ZCAN_ResetCAN(chn_handle)

    def GetReceiveNum(self, chn_handle, can_type=None):
        if can_type is None:
            can_type = c_uint(0)
        return self._dll.ZCAN_GetReceiveNum(chn_handle, can_type)

    def Transmit(self, chn_handle, std_msg, length):
        return self._dll.ZCAN_Transmit(chn_handle, byref(std_msg), length)

    def Receive(self, chn_handle, rcv_num, wait_time=None):
        if wait_time is None:
            wait_time = c_int(-1)
        rcv_msgs = (ZCAN_Receive_Data * rcv_num)()
        ret = self._dll.ZCAN_Receive(chn_handle, byref(rcv_msgs), rcv_num, wait_time)
        return rcv_msgs, ret
