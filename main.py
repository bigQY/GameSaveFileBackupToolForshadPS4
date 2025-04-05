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

            # 复制备份文件
            shutil.copytree(src_path, new_path)

            # 更新备份记录
            self.backups.append({
                "name": new_name,
                "date": datetime.now().isoformat(),
                "path": new_path
            })
            self.save_backups()
            self.update_backup_list()
            self.show_status(f"已创建副本：{new_name}")
        except Exception as e:
            messagebox.showerror("错误", f"创建副本失败：{str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = BackupManager(root)
    root.mainloop()