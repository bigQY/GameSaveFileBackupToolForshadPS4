#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
欢迎界面模块 - 首次使用时的配置向导
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog
from config.config_manager import ConfigManager

class WelcomeWindow:
    """欢迎界面类，用于首次使用时的配置"""
    
    def __init__(self, parent):
        """初始化欢迎界面
        
        Args:
            parent: 父窗口
        """
        self.window = tk.Toplevel(parent)
        
        # 先设置窗口属性
        self.window.title("欢迎使用 SaveGuard")
        self.window.geometry("800x600")
        self.window.resizable(False, False)
        self.window.transient(parent)
        
        # 设置窗口在屏幕中央
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        x = (screen_width - 800) // 2
        y = (screen_height - 600) // 2
        self.window.geometry(f"800x600+{x}+{y}")
        
        self.config_manager = ConfigManager()
        self.setup_ui()
        
        # 模态窗口
        self.window.grab_set()
        
    def setup_ui(self):
        """设置界面元素"""
        # 欢迎标题
        welcome_frame = ttk.Frame(self.window, padding="30 40 30 0")
        welcome_frame.pack(fill=tk.X)
        
        ttk.Label(
            welcome_frame,
            text="欢迎使用 SaveGuard 存档守护者",
            font=("Microsoft YaHei UI", 20, "bold")
        ).pack()
        
        ttk.Label(
            welcome_frame,
            text="请设置游戏存档位置和备份存储位置，开始使用程序",
            font=("Microsoft YaHei UI", 12)
        ).pack(pady=20)
        
        # 路径设置区域
        paths_frame = ttk.LabelFrame(self.window, text="路径设置", padding=30)
        paths_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=30)
        
        # 存档路径
        source_frame = ttk.Frame(paths_frame)
        source_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(source_frame, text="游戏存档位置：").pack(side=tk.LEFT)
        self.source_path_var = tk.StringVar(value=self.config_manager.config['paths']['source_path'])
        ttk.Entry(source_frame, textvariable=self.source_path_var, width=50).pack(side=tk.LEFT, padx=5)
        ttk.Button(source_frame, text="浏览", command=self.browse_source_path).pack(side=tk.LEFT)
        
        # 备份路径
        backup_frame = ttk.Frame(paths_frame)
        backup_frame.pack(fill=tk.X)
        
        ttk.Label(backup_frame, text="备份存储位置：").pack(side=tk.LEFT)
        self.backup_path_var = tk.StringVar(value=self.config_manager.config['paths']['backup_root'])
        ttk.Entry(backup_frame, textvariable=self.backup_path_var, width=50).pack(side=tk.LEFT, padx=5)
        ttk.Button(backup_frame, text="浏览", command=self.browse_backup_path).pack(side=tk.LEFT)
        
        # 说明文本
        ttk.Label(
            paths_frame,
            text="提示：请选择正确的游戏存档文件夹，备份文件将存储在指定的备份位置",
            font=("Microsoft YaHei UI", 9),
            foreground="gray"
        ).pack(pady=(20, 0))
        
        # 确认按钮
        ttk.Button(
            self.window,
            text="确认并开始使用",
            command=self.save_and_close,
            style="Accent.TButton"
        ).pack(pady=20)
        
        # 创建强调按钮样式
        style = ttk.Style()
        style.configure("Accent.TButton", font=("Microsoft YaHei UI", 10))
        
    def browse_source_path(self):
        """浏览选择存档路径"""
        path = filedialog.askdirectory(title="选择游戏存档位置")
        if path:
            self.source_path_var.set(path)
    
    def browse_backup_path(self):
        """浏览选择备份路径"""
        path = filedialog.askdirectory(title="选择备份存储位置")
        if path:
            self.backup_path_var.set(os.path.relpath(path))
    
    def save_and_close(self):
        """保存配置并关闭窗口"""
        source_path = self.source_path_var.get()
        backup_path = self.backup_path_var.get()
        
        if not source_path or not backup_path:
            tk.messagebox.showerror("错误", "请设置所有必要的路径")
            return
        
        if not os.path.exists(source_path):
            tk.messagebox.showerror("错误", "游戏存档位置不存在")
            return
        
        # 更新配置
        config = self.config_manager.config
        config['paths']['source_path'] = source_path
        config['paths']['backup_root'] = backup_path
        self.config_manager.update_config(config)
        
        self.window.destroy()