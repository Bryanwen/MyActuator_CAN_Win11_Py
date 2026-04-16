# -*- coding: utf-8 -*-
"""
CAN 通讯线程（CanWorker）
- 独立 daemon 线程，目标通讯周期 1 ms（实际频率受 USB/DLL 限制，通常 300-500 Hz）
- 主循环：
    1. 紧急停止检查 → 发送 0x80
    2. 发送 0x9C 读取双电机状态
    3. 非阻塞接收 → 解析 0x241/0x242 回复 → 更新 DataBus
    4. 若允许发送 → 按当前模式发送控制指令（0xA1/0xA2/0xA4）
    5. 精确等待至下一个 1ms 周期（若循环本身超时则立即进入下轮）
"""

import struct
import threading
import time

from kerneldlls.can_driver import open_device, send_frame, receive_frames, close_device

# ── 协议常量 ─────────────────────────────────────────────────────────────────
_CMD_READ = [0x9C, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
_CMD_STOP = [0x80, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]

_TX_IDS = {1: 0x141, 2: 0x142}   # 电机编号 → 发送 ID
_RX_IDS = {0x241: 1, 0x242: 2}   # 接收 ID → 电机编号

_PERIOD  = 0.001  # 1 ms 目标周期 → 上限由 USB/DLL 决定（约 300-500 Hz）
_HZ_WIN  = 30     # 每 30 次迭代统计一次实际频率（约 0.06-0.1 s 刷新一次 Hz 显示）
_MIN_SLEEP = 0.0001  # 最小让步睡眠，防止完全独占 CPU


class CanWorker(threading.Thread):
    """CAN 实时通讯线程"""

    def __init__(self, data_bus):
        super().__init__(daemon=True, name="CanWorker")
        self.db          = data_bus
        self._stop_evt   = threading.Event()
        self.device_name = "USBCAN-I"
        self.baud        = 1000000

    def stop(self):
        """请求线程安全退出"""
        self._stop_evt.set()

    # ── 线程主体 ─────────────────────────────────────────────────────────────

    def run(self):
        zcanlib = dev_handle = chn_handle = None
        try:
            zcanlib, dev_handle, chn_handle = open_device(
                device_name=self.device_name, baud=self.baud
            )
            self.db.set_status(
                True, f"已连接（{self.device_name}，{self.baud // 1000} kbps）"
            )

            iter_n = 0
            t_hz   = time.perf_counter()

            while not self._stop_evt.is_set():
                t0 = time.perf_counter()

                # ── 1. 紧急停止 ─────────────────────────────────────────────
                if self.db.consume_emergency_stop():
                    for tx in _TX_IDS.values():
                        send_frame(zcanlib, chn_handle, tx, _CMD_STOP)

                # ── 2. 发送读取指令 ──────────────────────────────────────────
                for tx in _TX_IDS.values():
                    send_frame(zcanlib, chn_handle, tx, _CMD_READ)

                # ── 3. 接收 & 解析 ───────────────────────────────────────────
                for can_id, data in receive_frames(zcanlib, chn_handle, max_count=64):
                    if can_id in _RX_IDS:
                        self._parse_status_reply(_RX_IDS[can_id], data)

                # ── 4. 发送控制指令 ──────────────────────────────────────────
                if self.db.is_send_enabled():
                    cmd = self.db.get_cmd()
                    for motor_id in (1, 2):
                        target  = cmd.m1_target if motor_id == 1 else cmd.m2_target
                        payload = self._build_ctrl_frame(cmd, target)
                        if payload:
                            send_frame(zcanlib, chn_handle, _TX_IDS[motor_id], payload)

                # ── 5. 频率统计 ──────────────────────────────────────────────
                iter_n += 1
                if iter_n >= _HZ_WIN:
                    dt = time.perf_counter() - t_hz
                    self.db.set_comm_hz(_HZ_WIN / dt if dt > 0 else 0.0)
                    t_hz   = time.perf_counter()
                    iter_n = 0

                # ── 6. 精确等待至下一个周期 ──────────────────────────────────
                sleep_t = _PERIOD - (time.perf_counter() - t0)
                if sleep_t > _MIN_SLEEP:
                    time.sleep(sleep_t)
                else:
                    # 循环已超时，仍让出一小片时间防止独占 CPU
                    time.sleep(_MIN_SLEEP)

        except Exception as exc:
            self.db.set_status(False, f"CAN 错误：{exc}")

        finally:
            if zcanlib is not None and dev_handle is not None and chn_handle is not None:
                try:
                    for tx in _TX_IDS.values():
                        send_frame(zcanlib, chn_handle, tx, _CMD_STOP)
                except Exception:
                    pass
                close_device(zcanlib, dev_handle, chn_handle)
            self.db.set_status(False, "已断开")
            self.db.set_send_enabled(False)
            self.db.set_comm_hz(0.0)

    # ── 协议解析 ─────────────────────────────────────────────────────────────

    def _parse_status_reply(self, motor_id: int, data: list):
        """
        解析 0x9C 回复帧（脉塔智能 V3）
          data[0]   = 0x9C
          data[1]   = 温度（°C）
          data[2:4] = ActualTorque   int16 LE，0.01 A/LSB
          data[4:6] = ActualVelocity int16 LE，1 dps/LSB
          data[6:8] = ActualPosition int16 LE，1 °/LSB
        """
        if len(data) < 8 or data[0] != 0x9C:
            return
        temp     = int(data[1])
        torque   = struct.unpack('<h', bytes(data[2:4]))[0] / 100.0  # A
        velocity = struct.unpack('<h', bytes(data[4:6]))[0] * 1.0    # dps
        position = struct.unpack('<h', bytes(data[6:8]))[0] * 1.0    # °
        self.db.update_motor(motor_id, position, velocity, torque, temp)

    # ── 控制帧构建 ────────────────────────────────────────────────────────────

    @staticmethod
    def _build_ctrl_frame(cmd, target: float) -> list:
        """
        速度模式 0xA2：
          [0xA2, max_torque_pct, 0, 0, v0..v3]
          TargetVelocity int32 LE，0.01 dps/LSB

        位置模式 0xA4：
          [0xA4, 0, spd_lo, spd_hi, p0..p3]
          max_velocity int16 LE，1 dps/LSB；TargetPosition int32 LE，0.01 °/LSB

        转矩模式 0xA1：
          [0xA1, 0, 0, 0, t0, t1, 0, 0]
          TargetTorque int16 LE，0.01 A/LSB
        """
        mode = cmd.mode
        if mode == "velocity":
            vel = struct.pack('<i', int(round(target * 100)))
            return [0xA2, int(cmd.max_torque_pct) & 0xFF, 0x00, 0x00] + list(vel)

        elif mode == "position":
            spd = struct.pack('<h', int(round(cmd.max_velocity)))
            pos = struct.pack('<i', int(round(target * 100)))
            return [0xA4, 0x00] + list(spd) + list(pos)

        elif mode == "torque":
            tor = struct.pack('<h', int(round(target * 100)))
            return [0xA1, 0x00, 0x00, 0x00] + list(tor) + [0x00, 0x00]

        return []

