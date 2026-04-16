# -*- coding: utf-8 -*-
"""
数据总线（DataBus）
所有线程共享数据的中转站，通过 threading.Lock 保证线程安全。

写入方：
  - CAN 通讯线程 → motor1/motor2 实时状态、连接状态、错误信息
  - GUI 线程     → 控制指令（模式/目标值）、是否启用发送

读取方：
  - CAN 通讯线程 → 控制指令
  - GUI 线程     → 电机状态、连接状态
"""

import threading
import time
from dataclasses import dataclass, field


@dataclass
class MotorState:
    """单台电机的实时状态"""
    position:    float = 0.0   # 实际位置，单位：°
    velocity:    float = 0.0   # 实际速度，单位：dps
    torque:      float = 0.0   # 实际转矩（电流），单位：A
    temperature: int   = 0     # 电机温度，单位：°C


@dataclass
class ControlCmd:
    """发送给电机的控制指令"""
    mode:           str   = "velocity"  # "torque" | "velocity" | "position"
    m1_target:      float = 0.0         # 电机 1 目标值
    m2_target:      float = 0.0         # 电机 2 目标值
    max_torque_pct: int   = 100         # 速度模式：最大转矩限制 0-255（%额定电流）
    max_velocity:   int   = 1000        # 位置模式：最大速度，单位 dps


class DataBus:
    """线程安全的全局数据总线"""

    def __init__(self):
        self._lock = threading.Lock()

        # ── 电机实时状态（CAN 线程写，GUI 线程读） ──────────────────────────
        self._motor: dict[int, MotorState] = {1: MotorState(), 2: MotorState()}

        # ── 控制指令（GUI 线程写，CAN 线程读） ────────────────────────────────
        self._cmd = ControlCmd()
        self._send_enabled: bool = False     # 是否持续发送控制指令

        # ── 连接/运行状态（CAN 线程写，GUI 线程读） ───────────────────────────
        self._connected:   bool = False
        self._status_msg:  str  = "未连接"
        self._update_ts:   float = 0.0       # 最近一次收到电机数据的时间戳
        self._comm_hz:     float = 0.0       # 实际通讯频率

        # ── 紧急停止标志（GUI 线程置位，CAN 线程读取后清零） ──────────────────
        self._emergency_stop: bool = False

    # ── 电机状态 ─────────────────────────────────────────────────────────────

    def update_motor(self, motor_id: int, position: float, velocity: float,
                     torque: float, temperature: int):
        with self._lock:
            s = self._motor[motor_id]
            s.position    = position
            s.velocity    = velocity
            s.torque      = torque
            s.temperature = temperature
            self._update_ts = time.monotonic()

    def get_motor(self, motor_id: int) -> MotorState:
        with self._lock:
            s = self._motor[motor_id]
            return MotorState(s.position, s.velocity, s.torque, s.temperature)

    # ── 控制指令 ─────────────────────────────────────────────────────────────

    def set_cmd(self, mode: str, m1_target: float, m2_target: float,
                max_torque_pct: int = 100, max_velocity: int = 1000):
        with self._lock:
            self._cmd.mode           = mode
            self._cmd.m1_target      = m1_target
            self._cmd.m2_target      = m2_target
            self._cmd.max_torque_pct = max_torque_pct
            self._cmd.max_velocity   = max_velocity

    def get_cmd(self) -> ControlCmd:
        with self._lock:
            c = self._cmd
            return ControlCmd(c.mode, c.m1_target, c.m2_target,
                              c.max_torque_pct, c.max_velocity)

    def set_send_enabled(self, enabled: bool):
        with self._lock:
            self._send_enabled = enabled

    def is_send_enabled(self) -> bool:
        with self._lock:
            return self._send_enabled

    # ── 紧急停止 ─────────────────────────────────────────────────────────────

    def request_emergency_stop(self):
        with self._lock:
            self._emergency_stop = True
            self._send_enabled   = False

    def consume_emergency_stop(self) -> bool:
        """CAN 线程调用：检查并清除紧急停止标志"""
        with self._lock:
            flag = self._emergency_stop
            self._emergency_stop = False
            return flag

    # ── 连接状态 ─────────────────────────────────────────────────────────────

    def set_status(self, connected: bool, msg: str):
        with self._lock:
            self._connected  = connected
            self._status_msg = msg

    def get_status(self) -> tuple:
        """返回 (connected: bool, status_msg: str)"""
        with self._lock:
            return self._connected, self._status_msg

    def set_comm_hz(self, hz: float):
        with self._lock:
            self._comm_hz = hz

    def get_comm_hz(self) -> float:
        with self._lock:
            return self._comm_hz
