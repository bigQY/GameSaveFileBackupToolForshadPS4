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
from i18n import get_i18n_manager, t


class BackupManagerUI:
    """备份管理器UI类，负责界面展示和用户交互"""
    
    def __init__(self, master):
        """初始化主窗口
        
        Args:
            master: tkinter主窗口
        """
        self.master = master
        master.title(t("app_title"))
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
        backup_frame = ttk.LabelFrame(main_frame, text=t("backup"), padding=10)
        backup_frame.grid(row=0, column=0, sticky="ew", pady=5)
        
        # 添加设置按钮和统计按钮
        buttons_frame = ttk.Frame(backup_frame)
        buttons_frame.pack(side=tk.RIGHT)
        
        ttk.Button(buttons_frame, text=t("storage_stats"), command=self.show_storage_stats).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text=t("settings"), command=self.show_settings).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(backup_frame, text=t("backup"), command=self.create_backup).pack(side=tk.LEFT)
        ttk.Label(backup_frame, text=t("backup_name") + ":").pack(side=tk.LEFT, padx=5)
        self.backup_name = ttk.Entry(backup_frame, width=25)
        self.backup_name.pack(side=tk.LEFT)

        # 备份列表
        list_frame = ttk.LabelFrame(main_frame, text=t("backup_list"), padding=10)
        list_frame.grid(row=1, column=0, sticky="nsew", pady=5)
        
        self.tree = ttk.Treeview(list_frame, columns=("name", "date", "path"), show="headings", height=8)
        self.tree.heading("name", text=t("backup_name"), anchor=tk.W)
        self.tree.heading("date", text=t("backup_date"), anchor=tk.W)
        self.tree.column("name", width=200)
        self.tree.column("date", width=150)
        self.tree.column("path", width=300)
        self.tree.pack(fill=tk.BOTH, expand=True)

        # 创建右键菜单
        self.context_menu = tk.Menu(self.master, tearoff=0)
        self.context_menu.add_command(label=t("rename"), command=self.rename_backup)
        self.context_menu.add_command(label=t("duplicate"), command=self.duplicate_backup)
        self.context_menu.add_separator()
        self.context_menu.add_command(label=t("delete"), command=self.delete_backup)

        # 绑定右键菜单
        self.tree.bind("<Button-3>", self.show_context_menu)

        # 滚动条
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 恢复操作区
        restore_frame = ttk.Frame(main_frame)
        restore_frame.grid(row=2, column=0, sticky="e", pady=5)
        ttk.Button(restore_frame, text=t("restore_selected"), command=self.restore_backup).pack(side=tk.RIGHT)

        # 状态栏
        self.status_bar = ttk.Label(main_frame, text=t("ready"), relief=tk.SUNKEN)
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
        backup_name = self.backup_name.get().strip() or t("unnamed_backup")
        success, message = self.backup_manager.create_backup(backup_name,is_manual=True)
        
        if success:
            self.update_backup_list()
            self.show_status(message)
            self.backup_name.delete(0, tk.END)
        else:
            messagebox.showerror(t("error"), message)
    
    def quick_backup(self):
        """快速备份功能"""
        success, message = self.backup_manager.quick_backup()
        
        if success:
            self.update_backup_list()
            self.show_status(message)
        else:
            self.master.after(0, lambda: messagebox.showerror(t("error"), message))
    
    def restore_backup(self):
        """恢复选中备份"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning(t("error"), t("select_backup_first"))
            return
            
        item = self.tree.item(selected[0])
        backup_path = item["values"][2]
        backup_name = item["values"][0]
        
        success, message = self.backup_manager.restore_backup(backup_path, backup_name,True)
        
        if success:
            self.show_status(message)
        else:
            messagebox.showerror(t("error"), message)
    
    def quick_restore(self):
        """快速恢复最新备份"""
        success, message = self.backup_manager.quick_restore()
        
        if success:
            self.show_status(message)
        else:
            self.master.after(0, lambda: messagebox.showerror(t("error"), message))
    
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
        self.master.after(3000, lambda: self.status_bar.config(text=t("ready")))
    
    def show_settings(self):
        """显示设置窗口"""
        settings_window = tk.Toplevel(self.master)
        settings_window.title(t('settings'))
        settings_window.geometry("500x550")
        settings_window.resizable(False, False)
        settings_window.transient(self.master)
        
        
        # 创建设置界面
        settings_frame = ttk.Frame(settings_window, padding=10)
        settings_frame.pack(fill=tk.BOTH, expand=True)
        
        # 快捷键设置
        hotkeys_frame = ttk.LabelFrame(settings_frame, text=t('hotkey_settings'), padding=10)
        hotkeys_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(hotkeys_frame, text=t('quick_backup') + '：').grid(row=0, column=0, sticky=tk.W)
        self.backup_key_label = ttk.Label(hotkeys_frame, text=self.config_manager.config['hotkeys']['quick_backup'], width=10, relief="sunken")
        self.backup_key_label.grid(row=0, column=1, padx=5)
        ttk.Button(hotkeys_frame, text=t('set'), command=lambda: self.start_key_listening('quick_backup')).grid(row=0, column=2)
        
        ttk.Label(hotkeys_frame, text=t('quick_restore') + '：').grid(row=1, column=0, sticky=tk.W)
        self.restore_key_label = ttk.Label(hotkeys_frame, text=self.config_manager.config['hotkeys']['quick_restore'], width=10, relief="sunken")
        self.restore_key_label.grid(row=1, column=1, padx=5)
        ttk.Button(hotkeys_frame, text=t('set'), command=lambda: self.start_key_listening('quick_restore')).grid(row=1, column=2)
        
        # 路径设置
        paths_frame = ttk.LabelFrame(settings_frame, text=t('path_settings'), padding=10)
        paths_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(paths_frame, text=t('save_directory') + '：').grid(row=0, column=0, sticky=tk.W)
        self.source_path_entry = ttk.Entry(paths_frame, width=30)
        self.source_path_entry.insert(0, self.config_manager.config['paths']['source_path'])
        self.source_path_entry.grid(row=0, column=1, padx=5)
        ttk.Button(paths_frame, text=t('browse'), command=lambda: self.browse_directory(self.source_path_entry)).grid(row=0, column=2)
        
        ttk.Label(paths_frame, text=t('backup_directory') + '：').grid(row=1, column=0, sticky=tk.W)
        self.backup_path_entry = ttk.Entry(paths_frame, width=30)
        self.backup_path_entry.insert(0, self.config_manager.config['paths']['backup_root'])
        self.backup_path_entry.grid(row=1, column=1, padx=5)
        ttk.Button(paths_frame, text=t('browse'), command=lambda: self.browse_directory(self.backup_path_entry)).grid(row=1, column=2)
        
        # 语言设置
        language_frame = ttk.LabelFrame(settings_frame, text=t('language_settings'), padding=10)
        language_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(language_frame, text=t('select_language') + '：').pack(side=tk.LEFT)
        self.language_var = tk.StringVar(value=self.config_manager.config.get('language', 'zh_CN'))
        language_combo = ttk.Combobox(language_frame, textvariable=self.language_var, state='readonly', width=15)
        language_combo['values'] = ['zh_CN', 'en_US']
        language_combo.pack(side=tk.LEFT, padx=5)
        
        # 功能设置
        features_frame = ttk.LabelFrame(settings_frame, text=t('feature_settings'), padding=10)
        features_frame.pack(fill=tk.X, pady=5)
        
        # MD5去重选项
        self.md5_var = tk.BooleanVar(value=self.config_manager.config['features']['md5_deduplication'])
        ttk.Checkbutton(features_frame, text=t('enable_md5_dedup'), 
                       variable=self.md5_var).pack(anchor=tk.W)
        
        # 自动载入选项
        self.auto_load_var = tk.BooleanVar(value=self.config_manager.config['features'].get('auto_load_after_restore', False))
        ttk.Checkbutton(features_frame, text=t('auto_load_after_restore'), 
                       variable=self.auto_load_var).pack(anchor=tk.W)
        
        # 自动保存选项
        self.auto_save_var = tk.BooleanVar(value=self.config_manager.config['features'].get('auto_save_before_backup', False))
        ttk.Checkbutton(features_frame, text=t('auto_save_before_backup'), 
                       variable=self.auto_save_var).pack(anchor=tk.W)
        
        # 添加保存按钮
        ttk.Button(settings_frame, text=t('save'), command=lambda: self.save_settings(settings_window, 
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
                    messagebox.showwarning(t("warning"), t("hotkey_already_used"))
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
            self.backup_key_label.config(text=t("press_key"))
        else:
            self.restore_key_label.config(text=t("press_key"))
    
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
        self.config_manager.config['features']['auto_save_before_backup'] = self.auto_save_var.get()
        
        # 更新语言设置
        new_language = self.language_var.get()
        old_language = self.config_manager.config.get('language', 'zh_CN')
        self.config_manager.config['language'] = new_language
        
        # 保存配置并重新加载
        self.config_manager.save_config()
        self.config_manager.update_config(self.config_manager.config)
        
        # 更新备份管理器的配置
        self.backup_manager = BackupManager(self.config_manager)
        self.update_backup_list()
        
        # 重新设置热键
        self.setup_hotkeys()
        
        # 如果语言发生变化，提示需要重启
        if new_language != old_language:
            messagebox.showinfo(t("language_changed_title"), t("language_changed_message"))
        
        # 关闭设置窗口
        settings_window.destroy()
        messagebox.showinfo(t("settings_saved_title"), t("settings_saved_message"))

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
            messagebox.showinfo(t("stats_info"), t("no_backup_data"))
            return
        
        # 显示统计信息
        stats_message = t("backup_count").format(count=stats['backup_count'], md5_count=stats['md5_backup_count'])
        stats_message += "\n\n" + t("repo_size").format(size=format_size(stats['repo_size']))
        stats_message += "\n" + t("total_files").format(count=stats['total_files'])
        stats_message += "\n" + t("theoretical_size").format(size=format_size(stats['theoretical_size']))
        stats_message += "\n\n" + t("saved_space").format(size=format_size(stats['saved_space']), percentage=stats['saved_percentage'])
        
        messagebox.showinfo(t("storage_stats"), stats_message)
    
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
        dialog.title(t("rename_backup"))
        dialog.geometry("300x100")
        dialog.transient(self.master)
        dialog.grab_set()

        ttk.Label(dialog, text=t("new_name") + "：").pack(pady=5)
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
                    messagebox.showerror(t("error"), message)
            dialog.destroy()

        ttk.Button(dialog, text=t("confirm"), command=do_rename).pack(pady=5)
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

        if messagebox.askyesno(t("confirm_delete"), t("confirm_delete_backup").format(backup_name=backup_name)):
            success, message = self.backup_manager.delete_backup(backup_path, backup_name)
            if success:
                self.update_backup_list()
                self.show_status(message)
            else:
                messagebox.showerror(t("error"), message)

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
            messagebox.showerror(t("error"), message)