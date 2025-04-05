#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
主窗口模块 - 提供应用程序的主界面
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import keyboard
from datetime import datetime

from config.config_manager import ConfigManager
from backup.backup_manager import BackupManager
from utils.system_utils import is_process_running, register_hotkey, unregister_all_hotkeys
from utils.file_utils import format_size


class BackupManagerUI:
    """备份管理器UI类，负责界面展示和用户交互"""
    
    def __init__(self, master):
        """初始化主窗口
        
        Args:
            master: tkinter主窗口
        """
        self.master = master
        master.title("SaveGuard v4.0 - 存档守护者")
        master.geometry("600x400")
        
        # 初始化配置管理器
        self.config_manager = ConfigManager()
        
        # 初始化备份管理器
        self.backup_manager = BackupManager(self.config_manager)
        
        # 创建界面
        self.create_widgets()
        self.update_backup_list()
        
        # 初始化热键
        self.setup_hotkeys()
        
        # 自动保存机制
        master.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def create_widgets(self):
        """创建界面组件"""
        # 主容器
        main_frame = ttk.Frame(self.master, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 备份操作区
        backup_frame = ttk.LabelFrame(main_frame, text="创建备份", padding=10)
        backup_frame.grid(row=0, column=0, sticky="ew", pady=5)
        
        # 添加设置按钮和统计按钮
        buttons_frame = ttk.Frame(backup_frame)
        buttons_frame.pack(side=tk.RIGHT)
        
        ttk.Button(buttons_frame, text="存储统计", command=self.show_storage_stats).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="设置", command=self.show_settings).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(backup_frame, text="新建备份", command=self.create_backup).pack(side=tk.LEFT)
        ttk.Label(backup_frame, text="备份名称：").pack(side=tk.LEFT, padx=5)
        self.backup_name = ttk.Entry(backup_frame, width=25)
        self.backup_name.pack(side=tk.LEFT)

        # 备份列表
        list_frame = ttk.LabelFrame(main_frame, text="备份列表", padding=10)
        list_frame.grid(row=1, column=0, sticky="nsew", pady=5)
        
        self.tree = ttk.Treeview(list_frame, columns=("name", "date", "path"), show="headings", height=8)
        self.tree.heading("name", text="备份名称", anchor=tk.W)
        self.tree.heading("date", text="备份时间", anchor=tk.W)
        self.tree.column("name", width=200)
        self.tree.column("date", width=150)
        self.tree.column("path", width=300)
        self.tree.pack(fill=tk.BOTH, expand=True)

        # 创建右键菜单
        self.context_menu = tk.Menu(self.master, tearoff=0)
        self.context_menu.add_command(label="重命名", command=self.rename_backup)
        self.context_menu.add_command(label="复制", command=self.duplicate_backup)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="删除", command=self.delete_backup)

        # 绑定右键菜单
        self.tree.bind("<Button-3>", self.show_context_menu)

        # 滚动条
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 恢复操作区
        restore_frame = ttk.Frame(main_frame)
        restore_frame.grid(row=2, column=0, sticky="e", pady=5)
        ttk.Button(restore_frame, text="恢复选中备份", command=self.restore_backup).pack(side=tk.RIGHT)

        # 状态栏
        self.status_bar = ttk.Label(main_frame, text="就绪", relief=tk.SUNKEN)
        self.status_bar.grid(row=3, column=0, sticky="ew")

        # 配置网格布局权重
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
    
    def setup_hotkeys(self):
        """注册全局热键"""
        def check_shadps4_running():
            return is_process_running('shadPS4.exe')
        
        # 注册热键
        self.hotkey_handlers = [
            register_hotkey(
                self.config_manager.config['hotkeys']['quick_backup'],
                lambda: self.master.after(0, self.quick_backup),
                check_shadps4_running
            ),
            register_hotkey(
                self.config_manager.config['hotkeys']['quick_restore'],
                lambda: self.master.after(0, self.quick_restore),
                check_shadps4_running
            )
        ]
    
    def create_backup(self):
        """创建新备份"""
        backup_name = self.backup_name.get().strip() or "未命名备份"
        success, message = self.backup_manager.create_backup(backup_name)
        
        if success:
            self.update_backup_list()
            self.show_status(message)
            self.backup_name.delete(0, tk.END)
        else:
            messagebox.showerror("错误", message)
    
    def quick_backup(self):
        """快速备份功能"""
        success, message = self.backup_manager.quick_backup()
        
        if success:
            self.update_backup_list()
            self.show_status(message)
        else:
            self.master.after(0, lambda: messagebox.showerror("错误", message))
    
    def restore_backup(self):
        """恢复选中备份"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择一个备份版本")
            return
            
        item = self.tree.item(selected[0])
        backup_path = item["values"][2]
        backup_name = item["values"][0]
        
        success, message = self.backup_manager.restore_backup(backup_path, backup_name)
        
        if success:
            self.show_status(message)
        else:
            messagebox.showerror("错误", message)
    
    def quick_restore(self):
        """快速恢复最新备份"""
        success, message = self.backup_manager.quick_restore()
        
        if success:
            self.show_status(message)
        else:
            self.master.after(0, lambda: messagebox.showerror("错误", message))
    
    def update_backup_list(self):
        """更新备份列表显示"""
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        for backup in sorted(self.backup_manager.backups, 
                           key=lambda x: x["date"], 
                           reverse=True):
            self.tree.insert("", tk.END, values=(
                backup["name"],
                datetime.fromisoformat(backup["date"]).strftime("%Y-%m-%d %H:%M:%S"),
                backup["path"]
            ))
    
    def show_status(self, message):
        """更新状态栏
        
        Args:
            message: 状态消息
        """
        self.status_bar.config(text=message)
        self.master.after(3000, lambda: self.status_bar.config(text="就绪"))
    
    def show_settings(self):
        """显示设置窗口"""
        settings_window = tk.Toplevel(self.master)
        settings_window.title("设置")
        settings_window.geometry("400x450")
        settings_window.resizable(False, False)
        settings_window.transient(self.master)
        
        # 创建设置界面
        settings_frame = ttk.Frame(settings_window, padding=10)
        settings_frame.pack(fill=tk.BOTH, expand=True)
        
        # 快捷键设置
        hotkeys_frame = ttk.LabelFrame(settings_frame, text="快捷键设置", padding=10)
        hotkeys_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(hotkeys_frame, text="快速备份：").grid(row=0, column=0, sticky=tk.W)
        self.backup_key_label = ttk.Label(hotkeys_frame, text=self.config_manager.config['hotkeys']['quick_backup'], width=10, relief="sunken")
        self.backup_key_label.grid(row=0, column=1, padx=5)
        ttk.Button(hotkeys_frame, text="设置", command=lambda: self.start_key_listening('quick_backup')).grid(row=0, column=2)
        
        ttk.Label(hotkeys_frame, text="快速恢复：").grid(row=1, column=0, sticky=tk.W)
        self.restore_key_label = ttk.Label(hotkeys_frame, text=self.config_manager.config['hotkeys']['quick_restore'], width=10, relief="sunken")
        self.restore_key_label.grid(row=1, column=1, padx=5)
        ttk.Button(hotkeys_frame, text="设置", command=lambda: self.start_key_listening('quick_restore')).grid(row=1, column=2)
        
        # 路径设置
        paths_frame = ttk.LabelFrame(settings_frame, text="路径设置", padding=10)
        paths_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(paths_frame, text="存档目录：").grid(row=0, column=0, sticky=tk.W)
        self.source_path_entry = ttk.Entry(paths_frame, width=30)
        self.source_path_entry.insert(0, self.config_manager.config['paths']['source_path'])
        self.source_path_entry.grid(row=0, column=1, padx=5)
        ttk.Button(paths_frame, text="浏览", command=lambda: self.browse_directory(self.source_path_entry)).grid(row=0, column=2)
        
        ttk.Label(paths_frame, text="备份目录：").grid(row=1, column=0, sticky=tk.W)
        self.backup_path_entry = ttk.Entry(paths_frame, width=30)
        self.backup_path_entry.insert(0, self.config_manager.config['paths']['backup_root'])
        self.backup_path_entry.grid(row=1, column=1, padx=5)
        ttk.Button(paths_frame, text="浏览", command=lambda: self.browse_directory(self.backup_path_entry)).grid(row=1, column=2)
        
        # 功能设置
        features_frame = ttk.LabelFrame(settings_frame, text="功能设置", padding=10)
        features_frame.pack(fill=tk.X, pady=5)
        
        # MD5去重选项
        self.md5_var = tk.BooleanVar(value=self.config_manager.config['features']['md5_deduplication'])
        ttk.Checkbutton(features_frame, text="启用MD5文件去重（节省存储空间）", 
                       variable=self.md5_var).pack(anchor=tk.W)
        
        # 自动载入选项
        self.auto_load_var = tk.BooleanVar(value=self.config_manager.config['features'].get('auto_load_after_restore', False))
        ttk.Checkbutton(features_frame, text="恢复后自动载入存档", 
                       variable=self.auto_load_var).pack(anchor=tk.W)
        
        # 添加保存按钮
        ttk.Button(settings_frame, text="保存", command=lambda: self.save_settings(settings_window, 
                                                                self.source_path_entry.get(),
                                                                self.backup_path_entry.get())).pack(pady=10)
    
    def start_key_listening(self, key_type):
        """开始监听键盘输入
        
        Args:
            key_type: 热键类型，'quick_backup' 或 'quick_restore'
        """
        # 先解除当前快捷键的绑定
        keyboard.remove_hotkey(self.config_manager.config['hotkeys'][key_type])
        
        def on_key_event(e):
            # 获取按键名称
            key_name = e.name
            if key_name not in ['shift', 'ctrl', 'alt']:
                # 检查按键是否已被使用
                other_key = 'quick_restore' if key_type == 'quick_backup' else 'quick_backup'
                if key_name == self.config_manager.config['hotkeys'][other_key]:
                    messagebox.showwarning("警告", "该快捷键已被其他功能使用")
                    return
                
                # 更新配置
                self.config_manager.config['hotkeys'][key_type] = key_name
                # 更新显示
                if key_type == 'quick_backup':
                    self.backup_key_label.config(text=key_name)
                else:
                    self.restore_key_label.config(text=key_name)
                # 移除监听器
                keyboard.unhook(hook)
                # 更新热键设置
                self.setup_hotkeys()
                
        # 添加按键监听
        hook = keyboard.on_press(on_key_event)
        
        # 更新状态提示
        if key_type == 'quick_backup':
            self.backup_key_label.config(text="请按键...")
        else:
            self.restore_key_label.config(text="请按键...")
    
    def save_settings(self, settings_window, source_path, backup_path):
        """保存设置
        
        Args:
            settings_window: 设置窗口
            source_path: 源路径
            backup_path: 备份路径
        """
        # 更新路径设置
        self.config_manager.config['paths']['source_path'] = source_path
        self.config_manager.config['paths']['backup_root'] = backup_path
        
        # 更新功能设置
        self.config_manager.config['features']['md5_deduplication'] = self.md5_var.get()
        self.config_manager.config['features']['auto_load_after_restore'] = self.auto_load_var.get()
        
        # 保存配置并重新加载
        self.config_manager.save_config()
        self.config_manager.update_config(self.config_manager.config)
        
        # 更新备份管理器的配置
        self.backup_manager = BackupManager(self.config_manager)
        self.update_backup_list()
        
        # 重新设置热键
        self.setup_hotkeys()
        
        # 关闭设置窗口
        settings_window.destroy()
        messagebox.showinfo("提示", "设置已保存")

    def browse_directory(self, entry_widget):
        """浏览文件夹
        
        Args:
            entry_widget: 要更新的输入框
        """
        directory = filedialog.askdirectory()
        if directory:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, directory)
            
    def show_storage_stats(self):
        """显示存储统计信息"""
        stats = self.backup_manager.calculate_storage_stats()
        if not stats:
            messagebox.showinfo("统计信息", "当前没有备份数据")
            return
        
        # 显示统计信息
        stats_message = f"备份总数: {stats['backup_count']} (MD5去重: {stats['md5_backup_count']})"
        stats_message += f"\n\n文件仓库大小: {format_size(stats['repo_size'])}"
        stats_message += f"\n备份文件总数: {stats['total_files']}"
        stats_message += f"\n理论占用空间: {format_size(stats['theoretical_size'])}"
        stats_message += f"\n\n节省空间: {format_size(stats['saved_space'])} ({stats['saved_percentage']:.1f}%)"
        
        messagebox.showinfo("存储统计", stats_message)
    
    def on_close(self):
        """窗口关闭时的清理"""
        unregister_all_hotkeys()
        self.master.destroy()

    def show_context_menu(self, event):
        """显示右键菜单
        
        Args:
            event: 鼠标事件
        """
        # 获取鼠标点击的项
        item = self.tree.identify_row(event.y)
        if item:
            # 选中被点击的项
            self.tree.selection_set(item)
            # 显示右键菜单
            self.context_menu.post(event.x_root, event.y_root)

    def rename_backup(self):
        """重命名备份"""
        selected = self.tree.selection()
        if not selected:
            return

        item = self.tree.item(selected[0])
        old_name = item['values'][0]
        old_path = item['values'][2]

        # 弹出重命名对话框
        dialog = tk.Toplevel(self.master)
        dialog.title("重命名备份")
        dialog.geometry("300x100")
        dialog.transient(self.master)
        dialog.grab_set()

        ttk.Label(dialog, text="新名称：").pack(pady=5)
        entry = ttk.Entry(dialog, width=30)
        entry.insert(0, old_name)
        entry.pack(pady=5)
        entry.select_range(0, tk.END)

        def do_rename():
            new_name = entry.get().strip()
            if new_name and new_name != old_name:
                success, message, _ = self.backup_manager.rename_backup(old_path, new_name)
                if success:
                    self.update_backup_list()
                    self.show_status(message)
                else:
                    messagebox.showerror("错误", message)
            dialog.destroy()

        ttk.Button(dialog, text="确定", command=do_rename).pack(pady=5)
        entry.bind("<Return>", lambda e: do_rename())
        entry.focus()

    def delete_backup(self):
        """删除备份"""
        selected = self.tree.selection()
        if not selected:
            return

        item = self.tree.item(selected[0])
        backup_name = item['values'][0]
        backup_path = item['values'][2]

        if messagebox.askyesno("确认删除", f"确定要删除备份 '{backup_name}' 吗？"):
            success, message = self.backup_manager.delete_backup(backup_path, backup_name)
            if success:
                self.update_backup_list()
                self.show_status(message)
            else:
                messagebox.showerror("错误", message)

    def duplicate_backup(self):
        """复制备份"""
        selected = self.tree.selection()
        if not selected:
            return

        item = self.tree.item(selected[0])
        src_name = item['values'][0]
        src_path = item['values'][2]

        success, message = self.backup_manager.duplicate_backup(src_path, src_name)
        if success:
            self.update_backup_list()
            self.show_status(message)
        else:
            messagebox.showerror("错误", message)