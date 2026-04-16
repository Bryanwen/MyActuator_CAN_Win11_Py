# motor_can_minimal

通过 ZLG USBCAN-I 接口向两个 RMD 系列电机（CAN ID 0x141 / 0x142）发送运行与停止指令的最简控制程序。

---

## 运行流程

| 步骤 | 动作 | CAN DATA |
|------|------|----------|
| 1 | 发送运行指令（转速 1） | `A2 00 00 00 10 27 00 00` |
| 2 | 等待 2 秒 | — |
| 3 | 发送运行指令（转速 2） | `A2 00 00 00 F0 D8 FF FF` |
| 4 | 等待 2 秒 | — |
| 5 | 发送停止指令 | `80 00 00 00 00 00 00 00` |
| 6 | 关闭 CAN 设备 | — |

两个电机（`0x141`、`0x142`）在每个步骤中同时发送。

---

## 目录结构

```
motor_can_minimal/
├── main_motor_run_stop.py          # 入口文件（唯一顶层 py）
└── kerneldlls/
    ├── __init__.py
    ├── zlgcan.py                   # ZLG DLL ctypes 封装层
    ├── can_driver.py               # CAN 设备操作封装（open/send/close）
    ├── zlgcan.dll                  # ZLG 主驱动 DLL（官方 SDK）
    └── kerneldlls/                 # zlgcan.dll 运行时依赖的子目录
        ├── dll_cfg.ini             # 设备类型 → 子 DLL 映射配置
        ├── USBCAN.dll              # USBCAN-I/II 专用子 DLL
        ├── CANDevCore.dll
        ├── CANDevice.dll
        ├── USBCAN.xml
        ├── VCI_USBCAN2.xml
        └── devices_property/
```

> **注意**：`kerneldlls/kerneldlls/` 这一层嵌套不可改变。  
> `zlgcan.dll` 在初始化时会从**自身所在目录**向下查找 `kerneldlls/dll_cfg.ini`，  
> 若该路径不存在则 `OpenDevice` 直接返回 0（无法找到设备）。

---

## 环境要求

### 硬件
- ZLG **USBCAN-I** 适配器，通过 USB 连接到 PC
- 两台支持 CAN 协议的 RMD 系列电机，CAN ID 分别为 `0x141`、`0x142`
- CAN 总线波特率：**1 Mbps**

### 软件

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10 / 11（64-bit） |
| Python | **3.8 或以上**（需要 `os.add_dll_directory` 支持） |
| 依赖库 | 仅标准库（`ctypes`、`time`、`os`、`platform`），**无需 pip 安装** |
| ZLG 驱动 | 需安装 ZLG 官方 USBCAN 驱动程序（安装后设备管理器中应正常显示设备） |

### ZLG 驱动安装

1. 前往 [ZLG 官网](https://www.zlg.cn) 下载 USBCAN 系列驱动包
2. 安装驱动后，将 USB 设备插入电脑
3. 打开设备管理器，确认出现 **USBCAN** 设备且无黄叹号

---

## 运行方式

```bash
# 在 motor_can_minimal/ 目录下执行
python main_motor_run_stop.py
```

---

## 常见问题

| 错误信息 | 原因 | 解决方法 |
|----------|------|----------|
| `打开设备失败！请检查 USB 连接和驱动。` | ZLG 驱动未安装 / USB 未连接 / 设备类型不匹配 | 安装官方驱动，检查 USB 连接，确认设备型号为 USBCAN-I |
| `初始化 CAN 通道失败！` | 波特率参数错误或设备已被其他程序占用 | 确认总线波特率为 1 Mbps，关闭其他 CAN 工具 |
| `启动 CAN 通道失败！` | CAN 总线未接终端电阻或线路故障 | 检查 CAN 总线接线及 120Ω 终端电阻 |
| `DLL 加载失败` | Python 版本低于 3.8 或 DLL 文件缺失 | 升级 Python 至 3.8+，确认 `kerneldlls/` 目录完整 |
