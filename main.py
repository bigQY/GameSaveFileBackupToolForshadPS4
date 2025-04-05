import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import shutil
import os
import json
from datetime import datetime
import psutil
import keyboard
import threading
import hashlib
from pathlib import Path
import win32gui
import win32con
import time

class BackupManager:
    def __init__(self, master):
        self.master = master
        master.title("存档管理工具 v4.0 - MD5去重版")
        master.geometry("600x400")
        
        # 加载配置文件
        self.config_file = "config.json"
        self.load_config()
        
        # 初始化路径和配置
        os.makedirs(self.backup_root, exist_ok=True)
        self.metadata_file = os.path.join(self.backup_root, "backups.json")
        
        # 初始化文件仓库路径
        self.file_repository = os.path.join(self.backup_root, "repository")
        os.makedirs(self.file_repository, exist_ok=True)
        
        # 加载备份记录
        self.backups = self.load_backups()
        
        # 创建界面
        self.create_widgets()
        self.update_backup_list()
        
        # 初始化热键
        self.setup_hotkeys()
        
        # 自动保存机制
        master.protocol("WM_DELETE_WINDOW", self.on_close)


    def create_widgets(self):
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
        def check_and_run(hotkey_func):
            def wrapper():
                if self.is_shadps4_running():
                    self.master.after(0, hotkey_func)
            return wrapper

        keyboard.add_hotkey(self.config['hotkeys']['quick_backup'], check_and_run(self.quick_backup))
        keyboard.add_hotkey(self.config['hotkeys']['quick_restore'], check_and_run(self.quick_restore))

    def is_shadps4_running(self):
        """检查模拟器进程是否在运行"""
        try:
            return any(p.info['name'] == 'shadPS4.exe' 
                      for p in psutil.process_iter(['name']))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def quick_backup(self):
        """快速备份功能"""
        if not os.path.exists(self.source_path):
            self.show_status("源目录不存在")
            return

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"快速备份_{timestamp}"
            backup_dir = os.path.join(self.backup_root, f"quick_{timestamp}")
            
            # 检查是否启用MD5去重
            use_md5 = self.config['features']['md5_deduplication']
            
            if use_md5:
                # MD5去重模式
                metadata_dir = os.path.join(backup_dir, "metadata")
                os.makedirs(metadata_dir, exist_ok=True)
                
                # 存储文件元数据信息
                file_metadata = []
                
                # 遍历源目录中的所有文件
                for root, _, files in os.walk(self.source_path):
                    for file in files:
                        src_file_path = os.path.join(root, file)
                        # 计算相对路径
                        rel_path = os.path.relpath(src_file_path, self.source_path)
                        
                        # 计算文件MD5
                        file_md5 = self.calculate_file_md5(src_file_path)
                        
                        # 仓库中的文件路径
                        repo_file_path = os.path.join(self.file_repository, file_md5)
                        
                        # 如果文件不在仓库中，则复制到仓库
                        if not os.path.exists(repo_file_path):
                            shutil.copy2(src_file_path, repo_file_path)
                        
                        # 记录文件元数据
                        file_metadata.append({
                            "path": rel_path,
                            "md5": file_md5,
                            "size": os.path.getsize(src_file_path),
                            "mtime": os.path.getmtime(src_file_path)
                        })
                
                # 保存文件元数据
                with open(os.path.join(metadata_dir, "files.json"), "w", encoding="utf-8") as f:
                    json.dump(file_metadata, f, ensure_ascii=False, indent=2)
                
                self.backups.append({
                    "name": backup_name,
                    "date": datetime.now().isoformat(),
                    "path": backup_dir,
                    "type": "md5"
                })
            else:
                # 传统模式 - 直接复制文件
                os.makedirs(backup_dir, exist_ok=True)
                data_dir = os.path.join(backup_dir, "data")
                shutil.copytree(self.source_path, data_dir)
                
                # 记录备份元数据
                self.backups.append({
                    "name": backup_name,
                    "date": datetime.now().isoformat(),
                    "path": backup_dir,
                    "type": "legacy"
                })
                
            self.save_backups()
            self.update_backup_list()
            self.show_status(f"快速备份成功：{backup_name}")
        except Exception as e:
            self.master.after(0, lambda: messagebox.showerror("错误", f"快速备份失败：{str(e)}"))
            import traceback
            traceback.print_exc()

    def quick_restore(self):
        """快速恢复最新备份"""
        if not self.backups:
            self.show_status("没有可用的备份")
            return

        try:
            latest = max(self.backups, key=lambda x: x["date"])
            backup_path = latest["path"]
            
            # 清空目标目录
            if os.path.exists(self.source_path):
                shutil.rmtree(self.source_path)
            os.makedirs(self.source_path, exist_ok=True)
            
            # 检查备份类型，处理MD5去重备份
            if latest.get("type") == "md5":
                metadata_file = os.path.join(backup_path, "metadata", "files.json")
                if not os.path.exists(metadata_file):
                    self.show_status("备份元数据文件不存在")
                    return
                
                # 加载文件元数据
                with open(metadata_file, "r", encoding="utf-8") as f:
                    file_metadata = json.load(f)
                
                # 根据元数据恢复文件
                for file_info in file_metadata:
                    # 目标文件路径
                    dest_file_path = os.path.join(self.source_path, file_info["path"])
                    # 确保目标目录存在
                    os.makedirs(os.path.dirname(dest_file_path), exist_ok=True)
                    
                    # 仓库中的文件路径
                    repo_file_path = os.path.join(self.file_repository, file_info["md5"])
                    
                    if os.path.exists(repo_file_path):
                        # 从仓库复制文件
                        shutil.copy2(repo_file_path, dest_file_path)
                        # 恢复文件的修改时间
                        os.utime(dest_file_path, (file_info["mtime"], file_info["mtime"]))
            else:
                # 处理旧版备份格式
                # 使用dirs_exist_ok=True参数允许目标目录已存在
                shutil.copytree(os.path.join(backup_path, "data"), self.source_path, dirs_exist_ok=True)
            
            self.show_status(f"已快速恢复：{latest['name']}")
            
            # 检查是否需要自动载入
            if self.config['features'].get('auto_load_after_restore', False):
                self.auto_load_game()
        except Exception as e:
            self.master.after(0, lambda: messagebox.showerror("错误", f"快速恢复失败：{str(e)}"))
            import traceback
            traceback.print_exc()

    def calculate_file_md5(self, file_path):
        """计算文件的MD5哈希值"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def create_backup(self):
        """创建新备份"""
        if not os.path.exists(self.source_path):
            messagebox.showerror("错误", "源目录不存在！")
            return

        backup_name = self.backup_name.get().strip() or "未命名备份"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join([c for c in backup_name if c not in r'\/:*?"<>|'])
        
        try:
            # 创建备份目录
            backup_dir = os.path.join(self.backup_root, f"{safe_name}_{timestamp}")
            
            # 检查是否启用MD5去重
            use_md5 = self.config['features']['md5_deduplication']
            
            if use_md5:
                # MD5去重模式
                metadata_dir = os.path.join(backup_dir, "metadata")
                os.makedirs(metadata_dir, exist_ok=True)
                
                # 存储文件元数据信息
                file_metadata = []
                
                # 遍历源目录中的所有文件
                for root, _, files in os.walk(self.source_path):
                    for file in files:
                        src_file_path = os.path.join(root, file)
                        # 计算相对路径
                        rel_path = os.path.relpath(src_file_path, self.source_path)
                        
                        # 计算文件MD5
                        file_md5 = self.calculate_file_md5(src_file_path)
                        
                        # 仓库中的文件路径
                        repo_file_path = os.path.join(self.file_repository, file_md5)
                        
                        # 如果文件不在仓库中，则复制到仓库
                        if not os.path.exists(repo_file_path):
                            shutil.copy2(src_file_path, repo_file_path)
                        
                        # 记录文件元数据
                        file_metadata.append({
                            "path": rel_path,
                            "md5": file_md5,
                            "size": os.path.getsize(src_file_path),
                            "mtime": os.path.getmtime(src_file_path)
                        })
                
                # 保存文件元数据
                with open(os.path.join(metadata_dir, "files.json"), "w", encoding="utf-8") as f:
                    json.dump(file_metadata, f, ensure_ascii=False, indent=2)
                
                # 记录备份元数据
                self.backups.append({
                    "name": backup_name,
                    "date": datetime.now().isoformat(),
                    "path": backup_dir,
                    "type": "md5"
                })
            else:
                # 传统模式 - 直接复制文件
                os.makedirs(backup_dir, exist_ok=True)
                data_dir = os.path.join(backup_dir, "data")
                shutil.copytree(self.source_path, data_dir)
                
                # 记录备份元数据
                self.backups.append({
                    "name": backup_name,
                    "date": datetime.now().isoformat(),
                    "path": backup_dir,
                    "type": "legacy"
                })
                
            self.save_backups()
            
            self.update_backup_list()
            self.show_status(f"备份成功：{backup_name}")
            self.backup_name.delete(0, tk.END)
        except Exception as e:
            messagebox.showerror("错误", f"备份失败：{str(e)}")
            import traceback
            traceback.print_exc()

    def restore_backup(self):
        """恢复选中备份"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择一个备份版本")
            return
            
        try:
            item = self.tree.item(selected[0])
            backup_path = item["values"][2]
            backup_name = item["values"][0]
            
            # 获取备份的详细信息
            backup_info = None
            for backup in self.backups:
                if backup["path"] == backup_path:
                    backup_info = backup
                    break
            
            if not backup_info:
                messagebox.showerror("错误", "找不到备份信息")
                return
            
            # 清空目标目录
            if os.path.exists(self.source_path):
                shutil.rmtree(self.source_path)
            os.makedirs(self.source_path, exist_ok=True)
            
            # 检查备份类型，处理MD5去重备份
            if backup_info.get("type") == "md5":
                metadata_file = os.path.join(backup_path, "metadata", "files.json")
                if not os.path.exists(metadata_file):
                    messagebox.showerror("错误", "备份元数据文件不存在")
                    return
                
                # 加载文件元数据
                with open(metadata_file, "r", encoding="utf-8") as f:
                    file_metadata = json.load(f)
                
                # 根据元数据恢复文件
                for file_info in file_metadata:
                    # 目标文件路径
                    dest_file_path = os.path.join(self.source_path, file_info["path"])
                    # 确保目标目录存在
                    os.makedirs(os.path.dirname(dest_file_path), exist_ok=True)
                    
                    # 仓库中的文件路径
                    repo_file_path = os.path.join(self.file_repository, file_info["md5"])
                    
                    if os.path.exists(repo_file_path):
                        # 从仓库复制文件
                        shutil.copy2(repo_file_path, dest_file_path)
                        # 恢复文件的修改时间
                        os.utime(dest_file_path, (file_info["mtime"], file_info["mtime"]))
                    else:
                        messagebox.showwarning("警告", f"仓库中找不到文件: {file_info['path']}")
            else:
                # 处理旧版备份格式
                # 使用dirs_exist_ok=True参数允许目标目录已存在
                shutil.copytree(os.path.join(backup_path, "data"), self.source_path, dirs_exist_ok=True)
            
            self.show_status(f"已从 {backup_name} 恢复存档")
            
            # 检查是否需要自动载入
            if self.config['features'].get('auto_load_after_restore', False):
                self.auto_load_game()
        except Exception as e:
            messagebox.showerror("错误", f"恢复失败：{str(e)}")
            import traceback
            traceback.print_exc()

    def update_backup_list(self):
        """更新备份列表显示"""
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        for backup in sorted(self.backups, 
                           key=lambda x: x["date"], 
                           reverse=True):
            self.tree.insert("", tk.END, values=(
                backup["name"],
                datetime.fromisoformat(backup["date"]).strftime("%Y-%m-%d %H:%M:%S"),
                backup["path"]
            ))

    def load_backups(self):
        """加载备份记录"""
        if os.path.exists(self.metadata_file):
            with open(self.metadata_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def save_backups(self):
        """保存备份记录"""
        with open(self.metadata_file, "w", encoding="utf-8") as f:
            json.dump(self.backups, f, ensure_ascii=False, indent=2)

    def show_status(self, message):
        """更新状态栏"""
        self.status_bar.config(text=message)
        self.master.after(3000, lambda: self.status_bar.config(text="就绪"))
        
    def load_config(self):
        """加载配置文件"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            else:
                self.config = {
                    'hotkeys': {'quick_backup': 'f7', 'quick_restore': 'f8'},
                    'paths': {
                        'source_path': r"D:\games\shadPS4\user\savedata\1\CUSA03023\SPRJ0005",
                        'backup_root': 'backups'
                    },
                    'features': {
                        'md5_deduplication': True
                    }
                }
                self.save_config()
        except Exception as e:
            messagebox.showerror("错误", f"加载配置文件失败：{str(e)}")
            self.config = {
                'hotkeys': {'quick_backup': 'f7', 'quick_restore': 'f8'},
                'paths': {
                    'source_path': r"D:\games\shadPS4\user\savedata\1\CUSA03023\SPRJ0005",
                    'backup_root': 'backups'
                },
                'features': {
                    'md5_deduplication': True
                }
            }
        
        self.source_path = self.config['paths']['source_path']
        self.backup_root = os.path.join(os.getcwd(), self.config['paths']['backup_root'])

    def auto_load_game(self):
        """自动载入游戏存档"""
        try:
            # 等待一段时间确保文件已经完全写入
            time.sleep(1)
            
            # 查找血源诅咒窗口
            hwnd = win32gui.FindWindow(None, "Bloodborne")
            if hwnd:
                # 激活窗口
                win32gui.SetForegroundWindow(hwnd)
                time.sleep(0.5)
                
                # 模拟按下OPTIONS键载入存档
                keyboard.press_and_release('esc')
                time.sleep(0.5)
                keyboard.press_and_release('enter')
                
                self.show_status("已自动载入存档")
            else:
                self.show_status("未找到游戏窗口，请手动载入存档")
        except Exception as e:
            self.show_status(f"自动载入失败：{str(e)}")
    
    def save_config(self):
        """保存配置文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            messagebox.showerror("错误", f"保存配置文件失败：{str(e)}")

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
        self.backup_key_label = ttk.Label(hotkeys_frame, text=self.config['hotkeys']['quick_backup'], width=10, relief="sunken")
        self.backup_key_label.grid(row=0, column=1, padx=5)
        ttk.Button(hotkeys_frame, text="设置", command=lambda: self.start_key_listening('quick_backup')).grid(row=0, column=2)
        
        ttk.Label(hotkeys_frame, text="快速恢复：").grid(row=1, column=0, sticky=tk.W)
        self.restore_key_label = ttk.Label(hotkeys_frame, text=self.config['hotkeys']['quick_restore'], width=10, relief="sunken")
        self.restore_key_label.grid(row=1, column=1, padx=5)
        ttk.Button(hotkeys_frame, text="设置", command=lambda: self.start_key_listening('quick_restore')).grid(row=1, column=2)
        
        # 路径设置
        paths_frame = ttk.LabelFrame(settings_frame, text="路径设置", padding=10)
        paths_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(paths_frame, text="存档目录：").grid(row=0, column=0, sticky=tk.W)
        self.source_path_entry = ttk.Entry(paths_frame, width=30)
        self.source_path_entry.insert(0, self.config['paths']['source_path'])
        self.source_path_entry.grid(row=0, column=1, padx=5)
        ttk.Button(paths_frame, text="浏览", command=lambda: self.browse_directory(self.source_path_entry)).grid(row=0, column=2)
        
        ttk.Label(paths_frame, text="备份目录：").grid(row=1, column=0, sticky=tk.W)
        self.backup_path_entry = ttk.Entry(paths_frame, width=30)
        self.backup_path_entry.insert(0, self.config['paths']['backup_root'])
        self.backup_path_entry.grid(row=1, column=1, padx=5)
        ttk.Button(paths_frame, text="浏览", command=lambda: self.browse_directory(self.backup_path_entry)).grid(row=1, column=2)
        
        # 功能设置
        features_frame = ttk.LabelFrame(settings_frame, text="功能设置", padding=10)
        features_frame.pack(fill=tk.X, pady=5)
        
        # MD5去重选项
        self.md5_var = tk.BooleanVar(value=self.config['features']['md5_deduplication'])
        ttk.Checkbutton(features_frame, text="启用MD5文件去重（节省存储空间）", 
                       variable=self.md5_var).pack(anchor=tk.W)
        
        # 自动载入选项
        self.auto_load_var = tk.BooleanVar(value=self.config['features'].get('auto_load_after_restore', False))
        ttk.Checkbutton(features_frame, text="恢复后自动载入存档", 
                       variable=self.auto_load_var).pack(anchor=tk.W)
        
        # 添加保存按钮
        ttk.Button(settings_frame, text="保存", command=lambda: self.save_settings(settings_window, 
                                                                self.source_path_entry.get(),
                                                                self.backup_path_entry.get())).pack(pady=10)

    def start_key_listening(self, key_type):
        """开始监听键盘输入"""
        # 先解除当前快捷键的绑定
        keyboard.remove_hotkey(self.config['hotkeys'][key_type])
        
        def on_key_event(e):
            # 获取按键名称
            key_name = e.name
            if key_name not in ['shift', 'ctrl', 'alt']:
                # 检查按键是否已被使用
                other_key = 'quick_restore' if key_type == 'quick_backup' else 'quick_backup'
                if key_name == self.config['hotkeys'][other_key]:
                    messagebox.showwarning("警告", "该快捷键已被其他功能使用")
                    return
                
                # 更新配置
                self.config['hotkeys'][key_type] = key_name
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
        """保存设置"""
        # 更新路径设置
        self.config['paths']['source_path'] = source_path
        self.config['paths']['backup_root'] = backup_path
        
        # 更新功能设置
        self.config['features']['md5_deduplication'] = self.md5_var.get()
        self.config['features']['auto_load_after_restore'] = self.auto_load_var.get()
        
        # 保存配置并重新加载
        self.save_config()
        self.load_config()
        self.setup_hotkeys()
        
        # 关闭设置窗口
        settings_window.destroy()
        messagebox.showinfo("提示", "设置已保存")

    def browse_directory(self, entry_widget):
        """浏览文件夹"""
        directory = filedialog.askdirectory()
        if directory:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, directory)
            
    def show_storage_stats(self):
        """显示存储统计信息"""
        if not self.backups:
            messagebox.showinfo("统计信息", "当前没有备份数据")
            return
            
        try:
            # 统计信息
            backup_count = len(self.backups)
            md5_backup_count = len([b for b in self.backups if b.get("type") == "md5"])
            
            # 计算仓库中的文件数量和总大小
            repo_files = os.listdir(self.file_repository)
            repo_size = sum(os.path.getsize(os.path.join(self.file_repository, f)) for f in repo_files)
            
            # 计算所有备份中的文件总数和理论大小（如果不去重）
            total_files = 0
            theoretical_size = 0
            
            for backup in self.backups:
                if backup.get("type") == "md5":
                    metadata_file = os.path.join(backup["path"], "metadata", "files.json")
                    if os.path.exists(metadata_file):
                        with open(metadata_file, "r", encoding="utf-8") as f:
                            file_metadata = json.load(f)
                            total_files += len(file_metadata)
                            theoretical_size += sum(file_info["size"] for file_info in file_metadata)
            
            # 计算节省的空间
            saved_space = theoretical_size - repo_size if theoretical_size > repo_size else 0
            saved_percentage = (saved_space / theoretical_size * 100) if theoretical_size > 0 else 0
            
            # 格式化大小显示
            def format_size(size_bytes):
                for unit in ['B', 'KB', 'MB', 'GB']:
                    if size_bytes < 1024 or unit == 'GB':
                        return f"{size_bytes:.2f} {unit}"
                    size_bytes /= 1024
            
            # 显示统计信息
            stats_message = f"备份总数: {backup_count} (MD5去重: {md5_backup_count})\n\n"
            stats_message += f"文件仓库大小: {format_size(repo_size)}\n"
            stats_message += f"备份文件总数: {total_files}\n"
            stats_message += f"理论占用空间: {format_size(theoretical_size)}\n\n"
            stats_message += f"节省空间: {format_size(saved_space)} ({saved_percentage:.1f}%)\n"
            
            messagebox.showinfo("存储统计", stats_message)
        except Exception as e:
            messagebox.showerror("错误", f"计算统计信息失败: {str(e)}")
            import traceback
            traceback.print_exc()

    def on_close(self):
        """窗口关闭时的清理"""
        keyboard.unhook_all_hotkeys()
        self.master.destroy()

    def show_context_menu(self, event):
        """显示右键菜单"""
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
                # 更新备份记录
                for backup in self.backups:
                    if backup['path'] == old_path:
                        backup['name'] = new_name
                        break
                self.save_backups()
                self.update_backup_list()
                self.show_status(f"已重命名：{old_name} -> {new_name}")
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
            try:
                # 删除备份文件
                shutil.rmtree(backup_path)
                # 更新备份记录
                self.backups = [b for b in self.backups if b['path'] != backup_path]
                self.save_backups()
                self.update_backup_list()
                self.show_status(f"已删除备份：{backup_name}")
            except Exception as e:
                messagebox.showerror("错误", f"删除失败：{str(e)}")

    def duplicate_backup(self):
        """复制备份"""
        selected = self.tree.selection()
        if not selected:
            return

        item = self.tree.item(selected[0])
        src_name = item['values'][0]
        src_path = item['values'][2]

        try:
            # 创建新的备份名称和路径
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_name = f"{src_name}_副本"
            new_path = os.path.join(self.backup_root, f"{new_name}_{timestamp}")
            
            # 获取源备份的详细信息
            src_backup = None
            for backup in self.backups:
                if backup["path"] == src_path:
                    src_backup = backup
                    break
                    
            if not src_backup:
                messagebox.showerror("错误", "找不到源备份信息")
                return
                
            # 检查备份类型
            if src_backup.get("type") == "md5":
                # 创建元数据目录
                metadata_dir = os.path.join(new_path, "metadata")
                os.makedirs(metadata_dir, exist_ok=True)
                
                # 复制元数据文件
                src_metadata_file = os.path.join(src_path, "metadata", "files.json")
                if os.path.exists(src_metadata_file):
                    with open(src_metadata_file, "r", encoding="utf-8") as f:
                        file_metadata = json.load(f)
                    
                    # 保存到新备份
                    with open(os.path.join(metadata_dir, "files.json"), "w", encoding="utf-8") as f:
                        json.dump(file_metadata, f, ensure_ascii=False, indent=2)
                else:
                    messagebox.showwarning("警告", "源备份的元数据文件不存在")
                    return
            else:
                # 旧版备份格式，直接复制
                shutil.copytree(src_path, new_path)

            # 更新备份记录
            self.backups.append({
                "name": new_name,
                "date": datetime.now().isoformat(),
                "path": new_path,
                "type": src_backup.get("type", "legacy")
            })
            self.save_backups()
            self.update_backup_list()
            self.show_status(f"已创建副本：{new_name}")
        except Exception as e:
            messagebox.showerror("错误", f"创建副本失败：{str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    root = tk.Tk()
    app = BackupManager(root)
    root.mainloop()