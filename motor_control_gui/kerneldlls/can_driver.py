# -*- coding: utf-8 -*-
"""
CAN 设备驱动封装（USBCAN-I/II，SJA1000 timing）
提供：打开设备、发送帧、非阻塞接收帧、关闭设备
"""

import struct
from ctypes import c_int, c_uint, memset, addressof, sizeof

from kerneldlls.zlgcan import (
    ZCAN, ZCAN_USBCAN1, ZCAN_USBCAN2,
    INVALID_DEVICE_HANDLE, INVALID_CHANNEL_HANDLE,
    ZCAN_STATUS_OK, ZCAN_CHANNEL_INIT_CONFIG,
    ZCAN_Transmit_Data,
)

# ── 波特率 timing 参数（SJA1000，USBCAN-I/II 专用）───────────────────────────
BAUD_TIMING = {
    1000000: (0x00, 0x14),
    500000:  (0x00, 0x1C),
    250000:  (0x01, 0x1C),
    125000:  (0x03, 0x1C),
    100000:  (0x04, 0x1C),
}

# 设备类型映射
DEVICE_TYPE_MAP = {
    "USBCAN-I":  ZCAN_USBCAN1,
    "USBCAN-II": ZCAN_USBCAN2,
}


def open_device(device_name="USBCAN-I", baud=1000000):
    """打开 USBCAN 设备并初始化通道 0，返回 (zcanlib, device_handle, chn_handle)"""
    dev_type = DEVICE_TYPE_MAP.get(device_name, ZCAN_USBCAN1)
    zcanlib = ZCAN()

    device_handle = zcanlib.OpenDevice(dev_type, 0, 0)
    if device_handle == INVALID_DEVICE_HANDLE:
        raise RuntimeError(f"打开设备 {device_name} 失败，请检查 USB 连接和驱动。")

    t0, t1 = BAUD_TIMING[baud]
    cfg = ZCAN_CHANNEL_INIT_CONFIG()
    cfg.can_type              = c_uint(0)   # CAN
    cfg.config.can.timing0    = t0
    cfg.config.can.timing1    = t1
    cfg.config.can.mode       = 0           # 正常模式
    cfg.config.can.acc_code   = 0
    cfg.config.can.acc_mask   = 0xFFFFFFFF

    chn_handle = zcanlib.InitCAN(device_handle, 0, cfg)
    if chn_handle == INVALID_CHANNEL_HANDLE:
        zcanlib.CloseDevice(device_handle)
        raise RuntimeError("初始化 CAN 通道失败。")

    ret = zcanlib.StartCAN(chn_handle)
    if ret != ZCAN_STATUS_OK:
        zcanlib.CloseDevice(device_handle)
        raise RuntimeError("启动 CAN 通道失败。")

    return zcanlib, device_handle, chn_handle


def send_frame(zcanlib, chn_handle, can_id: int, data: list) -> bool:
    """发送一帧标准 CAN 报文（8 字节），返回是否成功"""
    msg = (ZCAN_Transmit_Data * 1)()
    memset(addressof(msg), 0, sizeof(msg))
    msg[0].transmit_type   = 0
    msg[0].frame.can_id    = can_id
    msg[0].frame.can_dlc   = len(data)
    for i, b in enumerate(data):
        msg[0].frame.data[i] = b
    return zcanlib.Transmit(chn_handle, msg, 1) == 1


def receive_frames(zcanlib, chn_handle, max_count: int = 64) -> list:
    """
    非阻塞接收，返回 [(can_id, data_list), ...]
    can_id: 标准帧 ID
    data_list: list[int]，长度 = DLC
    """
    result = []
    try:
        n = zcanlib.GetReceiveNum(chn_handle, c_uint(0))
        if n <= 0:
            return result
        n = min(int(n), max_count)
        frames, count = zcanlib.Receive(chn_handle, n, wait_time=c_int(0))
        for i in range(int(count)):
            can_id = int(frames[i].frame.can_id) & 0x1FFFFFFF
            dlc    = int(frames[i].frame.can_dlc)
            data   = list(frames[i].frame.data[:dlc])
            result.append((can_id, data))
    except Exception:
        pass
    return result


def close_device(zcanlib, device_handle, chn_handle):
    """停止通道并关闭设备"""
    try:
        zcanlib.ResetCAN(chn_handle)
    except Exception:
        pass
    zcanlib.CloseDevice(device_handle)
