# motor_control_gui

脉塔智能 V3 驱动双电机实时控制系统。通过 ZLG USBCAN-I/II 接口，以 100 Hz 频率轮询读取双电机（CAN ID 0x141/0x142）的位置、速度、电流数据，并支持速度/位置/转矩三种模式的实时闭环控制。

---

## 目录结构

```
motor_control_gui/
├── main.py                     # 唯一入口，启动程序
├── shared/
│   └── data_bus.py             # 线程安全数据总线（所有线程共享数据在此中转）
├── can_comm/
│   └── can_worker.py           # CAN 通讯线程（100Hz，读取+控制）
├── gui/
│   └── main_window.py          # 软件显示界面（tkinter，主线程）
└── kerneldlls/
    ├── zlgcan.py               # ZLG DLL ctypes 封装（精简版）
    ├── can_driver.py           # open/send/receive/close 封装
    ├── [zlgcan.dll]            # ← 需从模板项目复制
    └── kerneldlls/             # ← 需从模板项目复制整个子目录
        ├── dll_cfg.ini
        ├── USBCAN.dll
        ├── CANDevCore.dll
        ├── CANDevice.dll
        ├── USBCAN.xml
        ├── VCI_USBCAN2.xml
        └── devices_property/
```

---

## 多线程架构

| 线程 | 位置 | 职责 |
|------|------|------|
| 主线程 | `gui/main_window.py` | tkinter GUI，每 100ms 刷新显示 |
| CanWorker（daemon）| `can_comm/can_worker.py` | 100Hz 收发，协议解析，写入 DataBus |
| 共享数据 | `shared/data_bus.py` | `threading.Lock` 保护，所有跨线程数据在此传递 |

---

## 环境要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10 / 11（64-bit） |
| Python | **≥ 3.8**（需要 `os.add_dll_directory`） |
| 依赖库 | 仅标准库（`ctypes`、`tkinter`、`struct`、`threading`、`time`）|
| ZLG 驱动 | ZLG 官方 USBCAN 驱动已安装，设备管理器中无黄叹号 |

---

## 首次配置（复制 DLL 文件）

新项目中没有 DLL 文件，需从 `motor_can_minimal` 模板项目复制：

```
# 复制 zlgcan.dll
motor_can_minimal/kerneldlls/zlgcan.dll
  → motor_control_gui/kerneldlls/zlgcan.dll

# 复制整个 kerneldlls 子目录
motor_can_minimal/kerneldlls/kerneldlls/
  → motor_control_gui/kerneldlls/kerneldlls/
```

复制完成后目录应如下：
```
kerneldlls/
├── zlgcan.py
├── can_driver.py
├── zlgcan.dll          ✓
└── kerneldlls/         ✓
    ├── dll_cfg.ini
    ├── USBCAN.dll
    └── ...
```

---

## 启动方式

```bash
cd motor_control_gui
python main.py
```

---

## 界面说明

### 连接配置
- **设备**：选择 USBCAN-I 或 USBCAN-II
- **波特率**：固定使用 1 Mbps（脉塔智能 V3 要求）
- **● 连接 / ○ 断开**：启动/停止 CanWorker 线程

### 实时状态
每 100ms 自动刷新双电机：
- **位置**：°（int16，1°/LSB）
- **速度**：dps（int16，1 dps/LSB）
- **电流**：A（int16，0.01 A/LSB）
- **温度**：°C

### 控制指令

| 模式 | 指令 | 目标值单位 | 辅助参数 |
|------|------|-----------|---------|
| 速度控制 | 0xA2 | dps | 最大转矩限制 0-255（%额定电流）|
| 位置控制 | 0xA4 | ° | 最大速度（dps）|
| 转矩控制 | 0xA1 | A | 无 |

- **▶ 开始控制**：持续每个通讯周期（10ms）向双电机发送指令
- **⬛ 紧急停止**：立即向双电机发送 0x80 停止指令，停止控制输出

---

## CAN 协议速查（脉塔智能 V3）

| 功能 | 发送 ID | 指令字节[0] | 说明 |
|------|---------|------------|------|
| 读取电机状态 | 0x141/0x142 | 0x9C | 回复 ID 0x241/0x242，含位置/速度/电流/温度 |
| 速度控制 | 0x141/0x142 | 0xA2 | int32 LE，0.01 dps/LSB |
| 位置控制 | 0x141/0x142 | 0xA4 | int32 LE，0.01°/LSB |
| 转矩控制 | 0x141/0x142 | 0xA1 | int16 LE，0.01 A/LSB |
| 停止电机 | 0x141/0x142 | 0x80 | 全零填充 |

---

## 常见问题

| 错误 | 原因 | 解决 |
|------|------|------|
| `找不到 zlgcan.dll` | DLL 未复制 | 按上方"首次配置"步骤复制 |
| `打开设备失败` | USB 未连或驱动未装 | 检查设备管理器，安装官方驱动 |
| `CAN 错误：初始化通道失败` | 设备被占用 | 关闭其他 CAN 工具 |
| 电机无响应 | 波特率或 ID 不匹配 | 确认电机 ID 为 0x141/0x142，总线波特率 1 Mbps |
