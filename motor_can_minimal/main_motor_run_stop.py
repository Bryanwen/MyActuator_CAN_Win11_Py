# -*- coding: utf-8 -*-
"""
电机运行-停止控制程序
1. 发送运行指令  (A2 00 00 00 10 27 00 00)
2. 保持 2 秒
3. 发送第二段运行指令 (A2 00 00 00 D8 F0 00 00)
4. 保持 2 秒
5. 发送停止指令  (80 00 00 00 00 00 00 00)
6. 关闭设备退出
"""

import time
from kerneldlls.can_driver import open_device, send_frame, close_device

# ── 主流程 ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":

    CMD_RUN  = [0xA2, 0x00, 0x00, 0x00, 0x10, 0x27, 0x00, 0x00]
    CMD_RUN2 = [0xA2, 0x00, 0x00, 0x00, 0xF0, 0xD8, 0xFF, 0xFF]
    CMD_STOP = [0x80, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]

    MOTOR_IDS  = [0x141, 0x142]
    RUN_TIME_S = 2.0

    try:
        zcanlib, dev_handle, chn_handle = open_device(baud=1000000)

        print("\n>>> 步骤 1：发送运行指令")
        results = [send_frame(zcanlib, chn_handle, mid, CMD_RUN, label=f"运行 ID=0x{mid:03X}") for mid in MOTOR_IDS]
        if not all(results):
            print("    部分帧发送失败，程序终止。")
        else:
            print(f"\n>>> 步骤 2：保持运行 {RUN_TIME_S} 秒...")
            time.sleep(RUN_TIME_S)

            print("\n>>> 步骤 3：发送第二段运行指令")
            results2 = [send_frame(zcanlib, chn_handle, mid, CMD_RUN2, label=f"运行2 ID=0x{mid:03X}") for mid in MOTOR_IDS]
            if not all(results2):
                print("    部分帧发送失败，程序终止。")
            else:
                print(f"\n>>> 步骤 4：保持运行 {RUN_TIME_S} 秒...")
                time.sleep(RUN_TIME_S)

                print("\n>>> 步骤 5：发送停止指令")
                for mid in MOTOR_IDS:
                    send_frame(zcanlib, chn_handle, mid, CMD_STOP, label=f"停止 ID=0x{mid:03X}")

        print("\n>>> 步骤 6：关闭设备")
        close_device(zcanlib, dev_handle, chn_handle)

    except Exception as e:
        print(f"\n[错误] {e}")

