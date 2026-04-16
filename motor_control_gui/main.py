# -*- coding: utf-8 -*-
"""
main.py — 程序唯一入口
启动顺序：
  1. 创建 DataBus（共享数据总线）
  2. 启动 GUI 主界面（主线程，tkinter 要求）
  GUI 内部按需创建并启动 CanWorker（daemon 线程）
"""

import sys
import os

# 确保项目根目录在模块搜索路径中（从任意工作目录运行均可）
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from shared.data_bus import DataBus
from can_comm.can_worker import CanWorker
from gui.main_window import MainWindow


def main():
    db = DataBus()

    def worker_factory(data_bus):
        """GUI 调用此工厂函数创建并返回新的 CanWorker 实例"""
        return CanWorker(data_bus)

    app = MainWindow(db, worker_factory)
    app.mainloop()


if __name__ == "__main__":
    main()
