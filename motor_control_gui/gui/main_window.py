# -*- coding: utf-8 -*-
"""
GUI 主界面（tkinter）
运行于主线程，通过 after() 回调每 100ms 刷新电机状态显示。

布局：
  ┌─ 连接配置 ──────────────────────────────────────────────────┐
  │  设备 [▼]  波特率 [▼]  [● 连接]  状态：未连接               │
  └─────────────────────────────────────────────────────────────┘
  ┌─ 实时状态 ──────────────────┬─ 实时状态 ──────────────────────┐
  │  电机 1                    │  电机 2                         │
  │  位置 / 速度 / 电流 / 温度  │  位置 / 速度 / 电流 / 温度       │
  └─────────────────────────────┴──────────────────────────────┘
  ┌─ 控制指令 ──────────────────────────────────────────────────┐
  │  模式：● 速度  ○ 位置  ○ 转矩                               │
  │  电机1目标: [____]   电机2目标: [____]   单位标签             │
  │  辅助参数（随模式显隐）                                        │
  │  [▶ 开始控制]   [⬛ 紧急停止]                               │
  └─────────────────────────────────────────────────────────────┘
  状态栏：● 已连接 | 通讯频率：100.0 Hz
"""

import tkinter as tk
from tkinter import ttk, messagebox


class MainWindow:
    """双电机实时控制主界面"""

    REFRESH_MS = 100  # GUI 刷新间隔（ms）

    def __init__(self, data_bus, worker_factory):
        """
        data_bus       : DataBus 实例
        worker_factory : 可调用对象，接收 data_bus 返回 CanWorker 实例
        """
        self.db             = data_bus
        self._worker_factory = worker_factory
        self._worker         = None

        self.root = tk.Tk()
        self.root.title("脉塔智能 V3 双电机实时控制系统")
        self.root.resizable(False, False)
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._schedule_refresh()

    def mainloop(self):
        self.root.mainloop()

    # ── UI 构建 ───────────────────────────────────────────────────────────────

    def _build_ui(self):
        pad = {"padx": 8, "pady": 6}

        # ── 连接配置 ─────────────────────────────────────────────────────────
        conn_frame = ttk.LabelFrame(self.root, text=" 连接配置 ")
        conn_frame.grid(row=0, column=0, columnspan=2, sticky="ew", **pad)

        ttk.Label(conn_frame, text="设备：").grid(row=0, column=0, sticky="w", padx=4)
        self._dev_var = tk.StringVar(value="USBCAN-I")
        ttk.Combobox(conn_frame, textvariable=self._dev_var, width=12,
                     values=["USBCAN-I", "USBCAN-II"], state="readonly"
                     ).grid(row=0, column=1, padx=4)

        ttk.Label(conn_frame, text="波特率：").grid(row=0, column=2, sticky="w", padx=4)
        self._baud_var = tk.StringVar(value="1000000")
        ttk.Combobox(conn_frame, textvariable=self._baud_var, width=10,
                     values=["1000000", "500000", "250000", "125000"],
                     state="readonly").grid(row=0, column=3, padx=4)

        self._conn_btn = ttk.Button(conn_frame, text="● 连接",
                                    command=self._on_connect, width=10)
        self._conn_btn.grid(row=0, column=4, padx=8)

        self._conn_status_lbl = ttk.Label(conn_frame, text="状态：未连接",
                                          foreground="gray")
        self._conn_status_lbl.grid(row=0, column=5, padx=8, sticky="w")

        # ── 双电机真实反馈数据（横向对比表） ──────────────────────────────────
        fb_frame = ttk.LabelFrame(
            self.root,
            text=" 双电机真实反馈数据  ★  自动刷新 10 Hz  ★  数据来源：CAN 回报帧 0x241/0x242 "
        )
        fb_frame.grid(row=1, column=0, columnspan=2, sticky="ew", **pad)

        # 表头行
        hfont = ("微软雅黑", 10, "bold")
        ttk.Label(fb_frame, text="参  数", font=hfont,
                  width=10, anchor="center").grid(row=0, column=0, padx=8, pady=6)
        for ci, mid in enumerate((1, 2)):
            ttk.Label(fb_frame,
                      text=f"电机 {mid}  ← 真实反馈",
                      font=hfont, anchor="center",
                      foreground="#003399"
                      ).grid(row=0, column=ci * 2 + 1, columnspan=2,
                             padx=12, pady=6, sticky="ew")
        ttk.Separator(fb_frame, orient="horizontal").grid(
            row=1, column=0, columnspan=5, sticky="ew", pady=2)

        # 数据行定义：(key, 行标签, 单位, 值背景色, 值字体)
        self._motor_lbl: dict[int, dict[str, tk.Label]] = {1: {}, 2: {}}
        _rows = [
            ("position", "实际位置", "°",   "#d0ecff", ("Consolas", 16, "bold")),
            ("velocity", "实际速度", "dps", "#d5f5d5", ("Consolas", 16, "bold")),
            ("torque",   "实际电流", "A",   "#fffacd", ("Consolas", 16, "bold")),
            ("temp",     "温    度", "°C",  "#ffe4d6", ("Consolas", 13)),
        ]
        for r, (key, name, unit, bg, vfont) in enumerate(_rows):
            ttk.Label(fb_frame, text=name, font=("微软雅黑", 10, "bold"),
                      width=10, anchor="e").grid(row=r + 2, column=0,
                                                  sticky="e", pady=8, padx=8)
            for ci, mid in enumerate((1, 2)):
                val_lbl = tk.Label(fb_frame, text="---",
                                   font=vfont, fg="#1a1a1a",
                                   width=11, anchor="e",
                                   bg=bg, relief="sunken", bd=2)
                val_lbl.grid(row=r + 2, column=ci * 2 + 1,
                             sticky="ew", pady=8, padx=(12, 0))
                tk.Label(fb_frame, text=unit, font=("微软雅黑", 9),
                         width=5, anchor="w").grid(row=r + 2, column=ci * 2 + 2,
                                                    sticky="w", padx=2)
                self._motor_lbl[mid][key] = val_lbl

        # ── 通讯线程实时状态 ───────────────────────────────────────────────────
        comm_mon = ttk.LabelFrame(self.root, text=" 通讯线程实时状态 ")
        comm_mon.grid(row=2, column=0, columnspan=2, sticky="ew", **pad)

        # 左侧：大字 Hz 显示
        hz_block = ttk.Frame(comm_mon)
        hz_block.grid(row=0, column=0, padx=20, pady=8)

        ttk.Label(hz_block, text="通讯频率", font=("微软雅黑", 9)
                  ).grid(row=0, column=0, columnspan=2)
        self._comm_dot_lbl = tk.Label(hz_block, text="●",
                                      font=("", 18), fg="gray")
        self._comm_dot_lbl.grid(row=1, column=0, padx=(0, 4))
        self._comm_hz_val  = tk.Label(hz_block, text="-- Hz",
                                      font=("Consolas", 24, "bold"),
                                      fg="gray", width=9, anchor="w")
        self._comm_hz_val.grid(row=1, column=1)

        # 分隔
        ttk.Separator(comm_mon, orient="vertical").grid(
            row=0, column=1, sticky="ns", padx=10, pady=4)

        # 右侧：频率区间说明
        legend_frame = ttk.Frame(comm_mon)
        legend_frame.grid(row=0, column=2, padx=10, pady=8, sticky="w")
        ttk.Label(legend_frame, text="频率状态说明：",
                  font=("微软雅黑", 9, "bold")).grid(row=0, column=0,
                                                  columnspan=2, sticky="w")
        legends = [
            ("●", "#00aa00", "≥ 80 Hz  正常"),
            ("●", "#cc8800", "20–80 Hz  偏低"),
            ("●", "#cc0000", "< 20 Hz  异常"),
            ("●", "gray",    "--- Hz  未连接"),
        ]
        for i, (dot, color, desc) in enumerate(legends):
            tk.Label(legend_frame, text=dot, fg=color,
                     font=("", 11)).grid(row=i + 1, column=0, sticky="w")
            ttk.Label(legend_frame, text=desc,
                      font=("微软雅黑", 9)).grid(row=i + 1, column=1, sticky="w",
                                               padx=4)

        # ── 控制指令面板 ──────────────────────────────────────────────────────
        ctrl_frame = ttk.LabelFrame(self.root, text=" 控制指令 ")
        ctrl_frame.grid(row=3, column=0, columnspan=2, sticky="ew", **pad)

        # 模式选择
        ttk.Label(ctrl_frame, text="控制模式：").grid(row=0, column=0, sticky="w",
                                                   padx=6, pady=4)
        self._mode_var = tk.StringVar(value="velocity")
        mode_options = [("速度控制 (dps)", "velocity"),
                        ("位置控制 (°)",  "position"),
                        ("转矩控制 (A)",  "torque")]
        for col, (text, val) in enumerate(mode_options):
            ttk.Radiobutton(ctrl_frame, text=text, variable=self._mode_var,
                            value=val, command=self._on_mode_change
                            ).grid(row=0, column=col + 1, padx=8, sticky="w")

        # 目标值输入
        target_row = ttk.Frame(ctrl_frame)
        target_row.grid(row=1, column=0, columnspan=5, sticky="ew", pady=4, padx=6)

        ttk.Label(target_row, text="电机1 目标：").grid(row=0, column=0, sticky="e")
        self._m1_target = tk.StringVar(value="0")
        ttk.Entry(target_row, textvariable=self._m1_target, width=12,
                  justify="right").grid(row=0, column=1, padx=4)
        self._m1_unit_lbl = ttk.Label(target_row, text="dps", width=5)
        self._m1_unit_lbl.grid(row=0, column=2, sticky="w")

        ttk.Label(target_row, text="电机2 目标：").grid(row=0, column=3, padx=(20, 0),
                                                     sticky="e")
        self._m2_target = tk.StringVar(value="0")
        ttk.Entry(target_row, textvariable=self._m2_target, width=12,
                  justify="right").grid(row=0, column=4, padx=4)
        self._m2_unit_lbl = ttk.Label(target_row, text="dps", width=5)
        self._m2_unit_lbl.grid(row=0, column=5, sticky="w")

        # 辅助参数行（随模式切换显隐）
        self._aux_frame = ttk.Frame(ctrl_frame)
        self._aux_frame.grid(row=2, column=0, columnspan=5, sticky="ew",
                             pady=2, padx=6)

        self._aux_lbl  = ttk.Label(self._aux_frame, text="最大转矩限制 (%)：")
        self._aux_lbl.grid(row=0, column=0, sticky="e")
        self._aux_var  = tk.StringVar(value="100")
        self._aux_entry = ttk.Entry(self._aux_frame, textvariable=self._aux_var,
                                    width=8, justify="right")
        self._aux_entry.grid(row=0, column=1, padx=4)
        ttk.Label(self._aux_frame, text="（速度模式：0-255；位置模式：最大速度 dps）"
                  ).grid(row=0, column=2, sticky="w", padx=4)

        # 按钮行
        btn_row = ttk.Frame(ctrl_frame)
        btn_row.grid(row=3, column=0, columnspan=5, pady=8)

        self._send_btn = ttk.Button(btn_row, text="▶  开始控制",
                                    command=self._on_toggle_send, width=14)
        self._send_btn.grid(row=0, column=0, padx=12)

        estop_btn = ttk.Button(btn_row, text="⬛  紧急停止",
                               command=self._on_estop, width=14,
                               style="Estop.TButton")
        estop_btn.grid(row=0, column=1, padx=12)

        # 紧急停止按钮红色样式
        style = ttk.Style()
        style.configure("Estop.TButton", foreground="red", font=("", 10, "bold"))

        # ── 状态栏 ────────────────────────────────────────────────────────────
        self._statusbar = ttk.Label(self.root, text="● 未连接  |  通讯频率：-- Hz",
                                    anchor="w", relief="sunken",
                                    foreground="gray", font=("", 9))
        self._statusbar.grid(row=4, column=0, columnspan=2, sticky="ew",
                             padx=0, pady=(0, 0))

        self.root.columnconfigure(0, weight=1)
        self.root.columnconfigure(1, weight=1)

    # ── 事件处理 ──────────────────────────────────────────────────────────────

    def _on_connect(self):
        connected, _ = self.db.get_status()
        if connected:
            # 断开
            self.db.request_emergency_stop()
            if self._worker:
                self._worker.stop()
                self._worker = None
            self._conn_btn.config(text="● 连接")
            self.db.set_send_enabled(False)
        else:
            # 连接
            self._worker = self._worker_factory(self.db)
            self._worker.device_name = self._dev_var.get()
            self._worker.baud        = int(self._baud_var.get())
            self._worker.start()
            self._conn_btn.config(text="○ 断开")

    def _on_mode_change(self):
        mode = self._mode_var.get()
        unit_map = {"velocity": "dps", "position": "°", "torque": "A"}
        unit = unit_map.get(mode, "")
        self._m1_unit_lbl.config(text=unit)
        self._m2_unit_lbl.config(text=unit)
        if mode == "velocity":
            self._aux_lbl.config(text="最大转矩限制 (%)：")
            self._aux_var.set("100")
        elif mode == "position":
            self._aux_lbl.config(text="最大速度 (dps)：")
            self._aux_var.set("1000")
        else:
            self._aux_lbl.config(text="（转矩模式无需辅助参数）")
            self._aux_var.set("0")
        # 停止当前发送
        self.db.set_send_enabled(False)
        self._send_btn.config(text="▶  开始控制")

    def _on_toggle_send(self):
        if not self.db.get_status()[0]:
            messagebox.showwarning("提示", "请先连接 CAN 设备。")
            return
        if self.db.is_send_enabled():
            # 停止发送
            self.db.set_send_enabled(False)
            self._send_btn.config(text="▶  开始控制")
        else:
            # 应用当前配置并启动发送
            if not self._apply_cmd():
                return
            self.db.set_send_enabled(True)
            self._send_btn.config(text="⏸  暂停控制")

    def _on_estop(self):
        self.db.request_emergency_stop()
        self._send_btn.config(text="▶  开始控制")

    def _apply_cmd(self) -> bool:
        """读取 GUI 输入并写入 DataBus，失败时弹出提示并返回 False"""
        try:
            m1 = float(self._m1_target.get())
            m2 = float(self._m2_target.get())
        except ValueError:
            messagebox.showerror("输入错误", "目标值必须为数字。")
            return False

        mode = self._mode_var.get()
        try:
            aux = int(float(self._aux_var.get()))
        except ValueError:
            aux = 100

        if mode == "velocity":
            self.db.set_cmd(mode, m1, m2, max_torque_pct=aux)
        elif mode == "position":
            self.db.set_cmd(mode, m1, m2, max_velocity=aux)
        else:
            self.db.set_cmd(mode, m1, m2)
        return True

    def _on_close(self):
        # 关闭前停止 CAN 线程
        self.db.request_emergency_stop()
        if self._worker:
            self._worker.stop()
        self.root.destroy()

    # ── 定时刷新 ──────────────────────────────────────────────────────────────

    def _schedule_refresh(self):
        self._refresh_display()
        self.root.after(self.REFRESH_MS, self._schedule_refresh)

    def _refresh_display(self):
        """读取 DataBus 并刷新所有显示控件"""
        connected, status_msg = self.db.get_status()
        hz = self.db.get_comm_hz()

        # 连接状态
        color = "#007700" if connected else "gray"
        self._conn_status_lbl.config(text=f"状态：{status_msg}", foreground=color)

        # 状态栏
        dot   = "●" if connected else "○"
        hz_str = f"{hz:.1f}" if hz > 0 else "--"
        self._statusbar.config(
            text=f"{dot} {status_msg}  |  通讯频率：{hz_str} Hz",
            foreground=color
        )

        # 通讯频率专用面板
        if not connected or hz <= 0:
            hz_color = "gray"
            hz_text  = "-- Hz"
        elif hz >= 80:
            hz_color = "#00aa00"
            hz_text  = f"{hz:.1f} Hz"
        elif hz >= 20:
            hz_color = "#cc8800"
            hz_text  = f"{hz:.1f} Hz"
        else:
            hz_color = "#cc0000"
            hz_text  = f"{hz:.1f} Hz"
        self._comm_hz_val.config(text=hz_text, fg=hz_color)
        self._comm_dot_lbl.config(fg=hz_color)

        # 按钮文字同步
        if not connected:
            self._conn_btn.config(text="● 连接")

        # 电机状态值颜色：未连接→灰色背景+破折号；已连接→各自原色
        field_bg = {
            "position": "#d0ecff",
            "velocity": "#d5f5d5",
            "torque":   "#fffacd",
            "temp":     "#ffe4d6",
        }
        field_bg_off = "#e8e8e8"  # 断线时统一灰底

        for motor_id, lbls in self._motor_lbl.items():
            s = self.db.get_motor(motor_id)
            if connected:
                lbls["position"].config(text=f"{s.position:+9.1f}",
                                        fg="#003366", bg=field_bg["position"])
                lbls["velocity"].config(text=f"{s.velocity:+9.1f}",
                                        fg="#003300", bg=field_bg["velocity"])
                lbls["torque"].config(text=f"{s.torque:+8.3f}",
                                      fg="#333300", bg=field_bg["torque"])
                lbls["temp"].config(text=f"{s.temperature:5d}",
                                    fg="#330000", bg=field_bg["temp"])
            else:
                for key, lbl in lbls.items():
                    lbl.config(text="---", fg="gray", bg=field_bg_off)
