#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
SaveGuard - 存档守护者
游戏存档备份管理工具的主程序入口
"""

import os
import tkinter as tk
from ui.main_window import BackupManagerUI
from ui.welcome_window import WelcomeWindow


def main():
    """程序入口函数"""
    root = tk.Tk()
    
    # 设置主窗口的基本属性
    root.title("SaveGuard - 存档守护者")
    root.geometry("900x600")
    
    # 检查配置文件是否存在
    if not os.path.exists("config.json"):
        welcome = WelcomeWindow(root)
        root.wait_window(welcome.window)
    
    root.deiconify()  # 显示主窗口
    app = BackupManagerUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
