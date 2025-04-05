import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import shutil
import os
import json
from datetime import datetime
import psutil
import keyboard
import threading

class BackupManager:
    def __init__(self, master):
        self.master = master
        master.title("存档管理工具 v3.0")
        master.geometry("600x400")
        master.resizable(False, False)
        
        # 加载配置文件
        self.config_file = "config.json"
        self.load_config()
        
        # 初始化路径和配置
        os.makedirs(self.backup_root, exist_ok=True)
        self.metadata_file = os.path.join(self.backup_root, "backups.json")
        
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
        
        # 添加设置按钮
        ttk.Button(backup_frame, text="设置", command=self.show_settings).pack(side=tk.RIGHT, padx=5)
        
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

        keyboard.unhook_all_hotkeys()
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
            
            os.makedirs(backup_dir, exist_ok=True)
            shutil.copytree(self.source_path, os.path.join(backup_dir, "data"))
            
            self.backups.append({
                "name": backup_name,
                "date": datetime.now().isoformat(),
                "path": backup_dir
            })
            self.save_backups()
            self.update_backup_list()
            self.show_status(f"快速备份成功：{backup_name}")
        except Exception as e:
            self.master.after(0, lambda: messagebox.showerror("错误", f"快速备份失败：{str(e)}"))

    def quick_restore(self):
        """快速恢复最新备份"""
        if not self.backups:
            self.show_status("没有可用的备份")
            return

        try:
            latest = max(self.backups, key=lambda x: x["date"])
            backup_path = os.path.join(latest["path"], "data")
            
            if os.path.exists(self.source_path):
                shutil.rmtree(self.source_path)
            shutil.copytree(backup_path, self.source_path)
            
            self.show_status(f"已快速恢复：{latest['name']}")
        except Exception as e:
            self.master.after(0, lambda: messagebox.showerror("错误", f"快速恢复失败：{str(e)}"))

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
            os.makedirs(backup_dir, exist_ok=True)
            
            # 复制文件
            shutil.copytree(self.source_path, os.path.join(backup_dir, "data"))
            
            # 记录元数据
            self.backups.append({
                "name": backup_name,
                "date": datetime.now().isoformat(),
                "path": backup_dir
            })
            self.save_backups()
            
            self.update_backup_list()
            self.show_status(f"备份成功：{backup_name}")
            self.backup_name.delete(0, tk.END)
        except Exception as e:
            messagebox.showerror("错误", f"备份失败：{str(e)}")

    def restore_backup(self):
        """恢复选中备份"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择一个备份版本")
            return
            
        try:
            item = self.tree.item(selected[0])
            backup_path = item["values"][2]
            
            # 清空目标目录
            if os.path.exists(self.source_path):
                shutil.rmtree(self.source_path)
                
            # 复制备份数据
            shutil.copytree(os.path.join(backup_path, "data"), self.source_path)
            
            self.show_status(f"已从 {item['values'][0]} 恢复存档")
        except Exception as e:
            messagebox.showerror("错误", f"恢复失败：{str(e)}")

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
                }
            }
        
        self.source_path = self.config['paths']['source_path']
        self.backup_root = os.path.join(os.getcwd(), self.config['paths']['backup_root'])

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
        settings_window.geometry("400x300")
        settings_window.resizable(False, False)
        settings_window.transient(self.master)
        
        # 创建设置界面
        settings_frame = ttk.Frame(settings_window, padding=10)
        settings_frame.pack(fill=tk.BOTH, expand=True)
        
        # 快捷键设置
        hotkeys_frame = ttk.LabelFrame(settings_frame, text="快捷键设置", padding=10)
        hotkeys_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(hotkeys_frame, text="快速备份：").grid(row=0, column=0, sticky=tk.W)
        backup_key = ttk.Entry(hotkeys_frame, width=10)
        backup_key.insert(0, self.config['hotkeys']['quick_backup'])
        backup_key.grid(row=0, column=1, padx=5)
        
        ttk.Label(hotkeys_frame, text="快速恢复：").grid(row=1, column=0, sticky=tk.W)
        restore_key = ttk.Entry(hotkeys_frame, width=10)
        restore_key.insert(0, self.config['hotkeys']['quick_restore'])
        restore_key.grid(row=1, column=1, padx=5)
        
        # 路径设置
        paths_frame = ttk.LabelFrame(settings_frame, text="路径设置", padding=10)
        paths_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(paths_frame, text="存档目录：").grid(row=0, column=0, sticky=tk.W)
        source_path = ttk.Entry(paths_frame, width=30)
        source_path.insert(0, self.config['paths']['source_path'])
        source_path.grid(row=0, column=1, padx=5)
        ttk.Button(paths_frame, text="浏览", command=lambda: self.browse_directory(source_path)).grid(row=0, column=2)
        
        ttk.Label(paths_frame, text="备份目录：").grid(row=1, column=0, sticky=tk.W)
        backup_path = ttk.Entry(paths_frame, width=30)
        backup_path.insert(0, self.config['paths']['backup_root'])
        backup_path.grid(row=1, column=1, padx=5)
        ttk.Button(paths_frame, text="浏览", command=lambda: self.browse_directory(backup_path)).grid(row=1, column=2)
        
        # 保存按钮
        def save_settings():
            self.config['hotkeys']['quick_backup'] = backup_key.get()
            self.config['hotkeys']['quick_restore'] = restore_key.get()
            self.config['paths']['source_path'] = source_path.get()
            self.config['paths']['backup_root'] = backup_path.get()
            
            self.save_config()
            self.load_config()
            self.setup_hotkeys()
            settings_window.destroy()
            messagebox.showinfo("提示", "设置已保存")
        
        ttk.Button(settings_frame, text="保存", command=save_settings).pack(pady=10)

    def browse_directory(self, entry_widget):
        """浏览文件夹"""
        directory = filedialog.askdirectory()
        if directory:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, directory)

    def on_close(self):
        """窗口关闭时的清理"""
        keyboard.unhook_all_hotkeys()
        self.master.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = BackupManager(root)
    root.mainloop()