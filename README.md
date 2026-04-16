# MyActuator_CAN — 脉塔电机 CAN 控制项目

> Windows 11 + ZLG USBCAN-I + 脉塔智能 RMD 系列电机  
> 两套程序：命令行最小示例 · 图形控制界面

---

## 目录

- [项目结构](#项目结构)
- [两个程序分别是什么](#两个程序分别是什么)
- [环境要求](#环境要求)
- [运行前准备（详细步骤）](#运行前准备详细步骤)
- [运行方式](#运行方式)
- [常见问题排查](#常见问题排查)
- [English Quick Start](#english-quick-start)

---

## 项目结构

```
MyActuator_CAN/
├── motor_can_minimal/              # 程序①：命令行最小示例
│   ├── main_motor_run_stop.py      # 唯一入口，直接运行
│   └── kerneldlls/                 # ZLG 驱动封装 + DLL 文件
│       ├── can_driver.py           # open / send / close 封装
│       ├── zlgcan.py               # ctypes 调用 zlgcan.dll
│       └── kerneldlls/             # zlgcan.dll 依赖的子目录（不可移动）
│
├── motor_control_gui/              # 程序②：图形界面控制程序
│   ├── main.py                     # 唯一入口，直接运行
│   ├── can_comm/
│   │   └── can_worker.py           # 后台 CAN 通讯线程（1 ms 周期）
│   ├── gui/
│   │   └── main_window.py          # tkinter 主窗口
│   └── shared/
│       └── data_bus.py             # 线程间共享数据总线
│
└── 必备运行环境/                    # ZLG 驱动安装包
    └── ZLGUSBCAN/
```

---

## 两个程序分别是什么

### 程序① `motor_can_minimal/main_motor_run_stop.py` — 命令行最小示例

**用途**：用最少的代码验证硬件连通性，执行一次完整的"启动 → 等待 → 换速 → 停止"动作序列。  
适合：初次调试、硬件验证、脚本化批量测试。

**执行流程**：

| 步骤 | 动作 | 发送帧 DATA（Hex） | 目标 ID |
|------|------|-------------------|---------|
| 1 | 发送运行指令（速度 1，正转 100 dps） | `A2 00 00 00 10 27 00 00` | 0x141 / 0x142 同时 |
| 2 | 等待 2 秒 | — | — |
| 3 | 发送运行指令（速度 2，反转 100 dps） | `A2 00 00 00 F0 D8 FF FF` | 0x141 / 0x142 同时 |
| 4 | 等待 2 秒 | — | — |
| 5 | 发送停止指令 | `80 00 00 00 00 00 00 00` | 0x141 / 0x142 同时 |
| 6 | 关闭 CAN 设备 | — | — |

**帧格式说明（命令 0xA2 速度模式）**：

```
字节 0     命令码  0xA2
字节 1     最大转矩百分比（0x00 = 默认）
字节 2-3   保留 0x0000
字节 4-7   目标速度 int32 LE，单位 0.01 dps/LSB
  → 0x00002710 = 10000 → 100.00 dps（正转）
  → 0xFFFFD8F0 = -10000 → -100.00 dps（反转）
```

---

### 程序② `motor_control_gui/main.py` — 图形界面实时控制系统

**用途**：提供可视化操作界面，实时显示两台电机的位置、速度、电流、温度，并支持速度 / 位置 / 转矩三种控制模式的实时指令发送。  
适合：日常手动调试、电机参数调整、演示展示。

**界面布局**：
```
┌─ 连接配置 ──────────────────────────────────────────────┐
│  设备 [USBCAN-I ▼]  波特率 [1000000 ▼]  [● 连接]        │
└─────────────────────────────────────────────────────────┘
┌─ 双电机真实反馈数据（自动刷新 10 Hz）───────────────────┐
│            电机 1（CAN 0x141）  电机 2（CAN 0x142）      │
│  实际位置   xxx.x °             xxx.x °                  │
│  实际速度   xxx.x dps           xxx.x dps                │
│  实际电流   x.xx A              x.xx A                   │
│  温    度   xx °C               xx °C                    │
└─────────────────────────────────────────────────────────┘
┌─ 通讯线程实时状态 ──────────────────────────────────────┐
│  通讯频率  ● 300.0 Hz  （≥80 Hz 绿色正常）               │
└─────────────────────────────────────────────────────────┘
┌─ 控制指令 ──────────────────────────────────────────────┐
│  模式：● 速度控制  ○ 位置控制  ○ 转矩控制               │
│  电机1 目标: [____] dps   电机2 目标: [____] dps         │
│  [▶ 开始控制]   [⬛ 紧急停止]                            │
└─────────────────────────────────────────────────────────┘
```

**后台通讯线程（`can_worker.py`）每 1 ms 执行一轮**：

1. 检查紧急停止标志 → 若触发立即向两台电机发送 `0x80` 停止帧
2. 向 0x141、0x142 发送 `0x9C` 读取状态指令
3. 接收 `0x241`/`0x242` 回报帧，解析位置/速度/电流/温度写入 DataBus
4. 若控制已启用，按当前模式发送控制指令：
   - 速度模式 `0xA2`：目标速度 int32 LE，0.01 dps/LSB
   - 位置模式 `0xA4`：最大速度 int16 LE + 目标位置 int32 LE，0.01°/LSB
   - 转矩模式 `0xA1`：目标电流 int16 LE，0.01 A/LSB
5. 精确等待至下一个 1 ms 周期（实际通讯频率约 300–500 Hz）

---

## 环境要求

### 硬件

- ZLG **USBCAN-I** 适配器（USB 连接至 PC）
- 两台脉塔 RMD 系列电机，CAN 节点 ID 分别为 **0x141**、**0x142**
- CAN 总线波特率：**1 Mbps**
- CAN 总线两端各一个 **120 Ω 终端电阻**

### 软件

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10 / 11（64-bit） |
| Python | **3.8 或以上**（需要 `os.add_dll_directory`） |
| 依赖库 | 程序① 仅标准库（`ctypes`、`time`、`os`）；程序② 额外需要 `tkinter`（Python 官方安装包自带） |
| ZLG 驱动 | 需安装 ZLG 官方 USBCAN 驱动（设备管理器中显示正常，无黄叹号） |

---

## 运行前准备（详细步骤）

### 第一步：安装 ZLG 驱动

1. 打开本仓库 `必备运行环境/ZLGUSBCAN/` 目录，运行驱动安装程序。
2. 插入 USB-CAN 设备，打开 **设备管理器**（Win+X → 设备管理器），确认出现 `USBCAN` 设备且**无黄叹号**。

### 第二步：确认 DLL 文件完整

两个程序各自的 `kerneldlls/` 目录需包含以下文件（ZLG 官方 SDK 提供）：

```
kerneldlls/
├── zlgcan.dll          ← 主驱动（必须与 Python 位宽一致：均为 64-bit）
├── zlgcan.py           ← ctypes 封装（已包含在本项目）
├── can_driver.py       ← 设备操作封装（已包含在本项目）
└── kerneldlls/         ← zlgcan.dll 的运行时依赖（目录名、位置不可改变）
    ├── dll_cfg.ini
    ├── USBCAN.dll
    ├── CANDevCore.dll
    ├── CANDevice.dll
    └── ...
```

> ⚠️ **重要**：`kerneldlls/kerneldlls/` 这层嵌套结构不可改变。  
> `zlgcan.dll` 启动时会在 **自身所在目录** 下查找 `kerneldlls/dll_cfg.ini`，  
> 路径不对将导致 `OpenDevice` 返回 0，设备无法打开。

### 第三步：安装 Python（如未安装）

1. 前往 [python.org](https://www.python.org/downloads/) 下载并安装 Python **3.8 或更高版本**。
2. 安装时勾选 **"Add Python to PATH"**。
3. 安装完成后验证：
   ```powershell
   python --version
   ```

### 第四步：确认 CAN 总线接线

- 将两台电机的 CAN H / CAN L 接到 USBCAN-I 对应端子
- 总线 **两端** 各接 **120 Ω 终端电阻**（缺少终端电阻会导致通信失败）
- 两台电机上电，确认节点 ID 配置为 **0x141** 和 **0x142**

---

## 运行方式

### 运行程序①（命令行最小示例）

```powershell
cd "C:\Users\Wen Hao\Desktop\MyActuator_CAN\motor_can_minimal"
python main_motor_run_stop.py
```

**预期输出**：
```
设备已打开，句柄: 1
CAN 通道已启动，通道句柄: 1，波特率: 1000 kbps

>>> 步骤 1：发送运行指令
  [运行 ID=0x141] 发送 ID=0x141  DATA: A2 00 00 00 10 27 00 00  →  成功
  [运行 ID=0x142] 发送 ID=0x142  DATA: A2 00 00 00 10 27 00 00  →  成功

>>> 步骤 2：保持运行 2.0 秒...

>>> 步骤 3：发送第二段运行指令
  [运行2 ID=0x141] 发送 ID=0x141  DATA: A2 00 00 00 F0 D8 FF FF  →  成功
  [运行2 ID=0x142] 发送 ID=0x142  DATA: A2 00 00 00 F0 D8 FF FF  →  成功

>>> 步骤 4：保持运行 2.0 秒...

>>> 步骤 5：发送停止指令
>>> 步骤 6：关闭设备
设备已关闭。
```

### 运行程序②（图形界面）

```powershell
cd "C:\Users\Wen Hao\Desktop\MyActuator_CAN\motor_control_gui"
python main.py
```

**操作步骤**：

1. 在界面顶部"连接配置"区选择设备（默认 `USBCAN-I`）与波特率（默认 `1000000`）。
2. 点击 **● 连接**，状态栏变为绿色"已连接"，通讯频率显示 300–500 Hz。
3. 观察"双电机真实反馈数据"区，确认两台电机的位置/速度/电流/温度已在刷新。
4. 在"控制指令"区选择控制模式并输入目标值：
   - **速度控制（dps）**：输入正数正转、负数反转，例如 `100` 或 `-100`，点击 **▶ 开始控制**。
   - **位置控制（°）**：输入目标角度，设置最大速度后点击 **▶ 开始控制**。
   - **转矩控制（A）**：输入目标电流值后点击 **▶ 开始控制**。
5. 需要立即停止时，点击 **⬛ 紧急停止**（后台线程立即发送 `0x80` 停止帧）。
6. 完成操作后点击 **断开** 或直接关闭窗口（程序自动发送停止帧并关闭设备）。

---

## 常见问题排查

| 错误信息 / 现象 | 可能原因 | 解决方法 |
|---------------|---------|---------|
| `打开设备失败！请检查 USB 连接和驱动。` | ZLG 驱动未安装 / USB 未连接 / 设备型号不匹配 | 安装官方驱动，检查 USB 连接，确认设备型号为 USBCAN-I |
| `初始化 CAN 通道失败！` | 波特率参数错误或设备被其他软件占用 | 确认总线波特率为 1 Mbps，关闭 ZCANPRO 等其他 CAN 工具 |
| `启动 CAN 通道失败！` | 总线无终端电阻或线路断路 | 检查接线，确认两端各有 120 Ω 终端电阻 |
| `DLL 加载失败` 或 `OSError` | Python 与 DLL 位宽不一致，或 DLL 文件缺失 | 确认均为 64-bit 版本，确认 `kerneldlls/` 目录完整 |
| 发送成功但电机无动作 | CAN ID 不对 / 电机未上电 / 节点 ID 配置错误 | 确认电机节点 ID 为 0x141/0x142，确认电机已上电 |
| GUI 通讯频率 < 20 Hz（红色） | USB 限速或 Python 进程负载过高 | 关闭其他高 CPU 占用程序，避免在调试器中单步执行 |
| 点击紧急停止后电机仍在转 | CAN 帧偶发丢失 | 检查总线接线，再次点击紧急停止，或重新连接设备 |

---

---

# English Quick Start

## What Are the Two Programs?

### Program 1 — `motor_can_minimal/main_motor_run_stop.py` (CLI Minimal Example)

**Purpose**: Verify hardware connectivity with minimal code. Runs a complete sequence: start → wait → change speed → stop, then closes the device.  
**Best for**: First-time hardware validation, scripted testing, debugging.

**Execution sequence**:

| Step | Action | CAN DATA (Hex) | Target IDs |
|------|--------|----------------|------------|
| 1 | Run command (speed 1, forward 100 dps) | `A2 00 00 00 10 27 00 00` | 0x141 + 0x142 simultaneously |
| 2 | Wait 2 seconds | — | — |
| 3 | Run command (speed 2, reverse 100 dps) | `A2 00 00 00 F0 D8 FF FF` | 0x141 + 0x142 simultaneously |
| 4 | Wait 2 seconds | — | — |
| 5 | Stop command | `80 00 00 00 00 00 00 00` | 0x141 + 0x142 simultaneously |
| 6 | Close CAN device | — | — |

**Frame format (0xA2 — Velocity mode)**:
```
Byte 0     Command code: 0xA2
Byte 1     Max torque % (0x00 = default)
Byte 2-3   Reserved 0x0000
Byte 4-7   Target velocity int32 LE, 0.01 dps/LSB
  → 0x00002710 = 10000 → 100.00 dps (forward)
  → 0xFFFFD8F0 = -10000 → -100.00 dps (reverse)
```

---

### Program 2 — `motor_control_gui/main.py` (GUI Real-time Controller)

**Purpose**: Visual interface for connecting to CAN, monitoring dual-motor feedback in real time, and sending velocity/position/torque commands interactively.  
**Best for**: Daily manual tuning, parameter adjustment, demos.

**Background thread** (`can_worker.py`) runs at ~1 ms cycle (actual ~300–500 Hz):
1. Check emergency stop flag → immediately send `0x80` to both motors if triggered
2. Send `0x9C` status query to motors 0x141 and 0x142
3. Receive `0x241`/`0x242` reply frames → parse position/velocity/current/temperature → write to DataBus
4. If control is enabled → send control frame based on mode:
   - Velocity `0xA2`: target speed int32 LE, 0.01 dps/LSB
   - Position `0xA4`: max velocity int16 LE + target position int32 LE, 0.01°/LSB
   - Torque `0xA1`: target current int16 LE, 0.01 A/LSB
5. Sleep precisely to maintain ~1 ms period

---

## Hardware Requirements

- ZLG **USBCAN-I** adapter (USB to PC)
- Two RMD-series motors with CAN node IDs **0x141** and **0x142**
- CAN bus bitrate: **1 Mbps**
- **120 Ω** termination resistors at **both ends** of the CAN bus

## Software Requirements

| Item | Requirement |
|------|------------|
| OS | Windows 10 / 11 (64-bit) |
| Python | **3.8+** (requires `os.add_dll_directory`) |
| Libraries | Program 1: stdlib only. Program 2: `tkinter` (bundled with Python) |
| ZLG Driver | Official USBCAN driver installed; device appears normally in Device Manager |

---

## Step-by-Step Setup

**Step 1 — Install ZLG driver**  
Run the installer from `必备运行环境/ZLGUSBCAN/`. Plug in the USB-CAN device and confirm it appears in Device Manager with no yellow warning icon.

**Step 2 — Verify DLL files**  
Each program's `kerneldlls/` must contain `zlgcan.dll` and all dependencies inside the nested `kerneldlls/kerneldlls/` subfolder. **Do not rename or move this nested folder** — `zlgcan.dll` searches for `kerneldlls/dll_cfg.ini` relative to its own location at startup.

**Step 3 — Install Python 3.8+**  
Download from [python.org](https://www.python.org/downloads/). Check **"Add Python to PATH"** during install.

```powershell
python --version   # verify
```

**Step 4 — Wire the CAN bus**  
Connect motor CAN H/L to USBCAN-I terminals. Add **120 Ω** termination at both ends of the bus. Power on the motors and confirm node IDs are **0x141** and **0x142**.

---

## Running the Programs

### CLI example

```powershell
cd "C:\Users\Wen Hao\Desktop\MyActuator_CAN\motor_can_minimal"
python main_motor_run_stop.py
```

### GUI controller

```powershell
cd "C:\Users\Wen Hao\Desktop\MyActuator_CAN\motor_control_gui"
python main.py
```

**GUI usage**:
1. Select device (`USBCAN-I`) and bitrate (`1000000`), click **● Connect**.
2. Confirm the feedback panel shows live data for both motors (position/velocity/current/temperature).
3. Choose control mode, enter target values, click **▶ Start Control**.
4. Click **⬛ Emergency Stop** at any time to immediately halt motors (`0x80` frame sent).
5. Click **Disconnect** or close the window — the program automatically sends stop frames and closes the device.

---

## Troubleshooting

| Error / Symptom | Likely Cause | Fix |
|----------------|-------------|-----|
| `打开设备失败` / Open device failed | Driver not installed, USB disconnected, wrong device model | Install official driver, check USB, confirm USBCAN-I |
| Init CAN channel failed | Wrong bitrate or device occupied by another app | Set bitrate to 1 Mbps, close ZCANPRO or other CAN tools |
| Start CAN channel failed | Missing termination resistor or broken bus wiring | Check wiring and confirm 120 Ω termination at both ends |
| DLL load error / `OSError` | Bitness mismatch (32-bit DLL with 64-bit Python) or missing files | Use matching 64-bit DLL; verify `kerneldlls/` is complete |
| Send OK but motor does not move | Wrong node ID or motor not powered | Confirm IDs are 0x141/0x142; confirm motor power supply |
| GUI frequency < 20 Hz (red) | High CPU load or USB bottleneck | Close CPU-heavy apps; avoid stepping through debugger |
| Emergency stop not responding | Occasional CAN frame loss | Check bus wiring; click Emergency Stop again or reconnect |
