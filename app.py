#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
SaveGuard - 存档守护者
游戏存档备份管理工具的主程序入口
"""

import tkinter as tk
from ui.main_window import BackupManagerUI


def main():
    """程序入口函数"""
    root = tk.Tk()
    app = BackupManagerUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
