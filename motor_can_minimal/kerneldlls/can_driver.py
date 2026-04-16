# -*- coding: utf-8 -*-
"""
CAN 设备驱动封装（USBCAN-I/II，SJA1000 timing）
"""

from kerneldlls.zlgcan import (
    ZCAN, ZCAN_USBCAN1, INVALID_DEVICE_HANDLE, INVALID_CHANNEL_HANDLE,
    ZCAN_STATUS_OK, ZCAN_TYPE_CAN, ZCAN_CHANNEL_INIT_CONFIG,
    ZCAN_Transmit_Data, memset, addressof, sizeof,
)
from ctypes import c_uint

# 波特率 timing 参数（SJA1000，USBCAN-I/II 专用）
BAUD_TIMING = {
    1000000: (0x00, 0x14),
    500000:  (0x00, 0x1C),
    250000:  (0x01, 0x1C),
    125000:  (0x03, 0x1C),
    100000:  (0x04, 0x1C),
}


def open_device(baud=1000000):
    """打开 USBCAN-I 设备并初始化通道 0，返回 (zcanlib, device_handle, chn_handle)"""
    zcanlib = ZCAN()

    device_handle = zcanlib.OpenDevice(ZCAN_USBCAN1, 0, 0)
    if device_handle == INVALID_DEVICE_HANDLE:
        raise RuntimeError("打开设备失败！请检查 USB 连接和驱动。")
    print(f"设备已打开，句柄: {device_handle}")

    t0, t1 = BAUD_TIMING[baud]
    cfg = ZCAN_CHANNEL_INIT_CONFIG()
    cfg.can_type = c_uint(0)            # ZCAN_TYPE_CAN
    cfg.config.can.timing0  = t0
    cfg.config.can.timing1  = t1
    cfg.config.can.mode     = 0
    cfg.config.can.acc_code = 0
    cfg.config.can.acc_mask = 0xFFFFFFFF

    chn_handle = zcanlib.InitCAN(device_handle, 0, cfg)
    if chn_handle == INVALID_CHANNEL_HANDLE:
        zcanlib.CloseDevice(device_handle)
        raise RuntimeError("初始化 CAN 通道失败！")

    ret = zcanlib.StartCAN(chn_handle)
    if ret != ZCAN_STATUS_OK:
        zcanlib.CloseDevice(device_handle)
        raise RuntimeError("启动 CAN 通道失败！")

    print(f"CAN 通道已启动，通道句柄: {chn_handle}，波特率: {baud // 1000} kbps")
    return zcanlib, device_handle, chn_handle


def send_frame(zcanlib, chn_handle, can_id: int, data: list, label: str = ""):
    """发送一帧标准 CAN 报文（最多 8 字节）"""
    msg = (ZCAN_Transmit_Data * 1)()
    memset(addressof(msg), 0, sizeof(msg))
    msg[0].transmit_type = 0
    msg[0].frame.can_id  = can_id
    msg[0].frame.can_dlc = len(data)
    for i, b in enumerate(data):
        msg[0].frame.data[i] = b

    ret = zcanlib.Transmit(chn_handle, msg, 1)
    data_str = " ".join(f"{b:02X}" for b in data)
    status   = "成功" if ret == 1 else f"失败(ret={ret})"
    print(f"  [{label}] 发送 ID=0x{can_id:03X}  DATA: {data_str}  →  {status}")
    return ret == 1


def close_device(zcanlib, device_handle, chn_handle):
    """停止通道并关闭设备"""
    zcanlib.ResetCAN(chn_handle)
    ret = zcanlib.CloseDevice(device_handle)
    print("设备已关闭。" if ret == 1 else "关闭设备失败。")
