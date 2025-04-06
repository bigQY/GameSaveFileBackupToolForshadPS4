#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
备份管理模块 - 负责处理备份和恢复操作
"""

import os
import json
import shutil
from datetime import datetime
from tkinter import messagebox

from utils.file_utils import calculate_file_md5, ensure_dir, safe_filename
from utils.system_utils import simulate_key_press

import win32gui
import win32con

def focus_window(window_title):
    """模糊匹配窗口标题并聚焦窗口，使用增强的窗口激活方法"""
    def enum_windows_callback(hwnd, results):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if window_title.lower() in title.lower():  # 模糊匹配
                results.append(hwnd)

    results = []
    win32gui.EnumWindows(enum_windows_callback, results)
    if results:
        hwnd = results[0]
        # 尝试多种方法激活窗口
        try:
            # 确保窗口不是最小化的
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            # 将窗口置于前台
            win32gui.SetForegroundWindow(hwnd)
            # 额外尝试置顶窗口
            win32gui.BringWindowToTop(hwnd)
            # 使用ALT+TAB切换到窗口
            import time
            time.sleep(0.1)
            # 尝试再次激活窗口
            win32gui.SetForegroundWindow(hwnd)
            # 给系统更多时间来响应
            time.sleep(0.1)
            return True
        except Exception as e:
            print(f"激活窗口失败: {str(e)}")
            return False
    return False


class BackupManager:
    """备份管理类，负责处理备份和恢复操作"""
    
    def __init__(self, config_manager):
        """初始化备份管理器
        
        Args:
            config_manager: 配置管理器实例
        """
        self.config_manager = config_manager
        self.config = config_manager.config
        self.source_path = config_manager.source_path
        self.backup_root = config_manager.backup_root
        
        # 确保备份根目录存在
        ensure_dir(self.backup_root)
        
        # 初始化文件仓库路径
        self.file_repository = os.path.join(self.backup_root, "repository")
        ensure_dir(self.file_repository)
        
        # 备份元数据文件
        self.metadata_file = os.path.join(self.backup_root, "backups.json")
        
        # 加载备份记录
        self.backups = self.load_backups()
    
    def load_backups(self):
        """加载备份记录
        
        Returns:
            list: 备份记录列表
        """
        if os.path.exists(self.metadata_file):
            with open(self.metadata_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return []
    
    def save_backups(self):
        """保存备份记录"""
        with open(self.metadata_file, "w", encoding="utf-8") as f:
            json.dump(self.backups, f, ensure_ascii=False, indent=2)
    
    def create_backup(self, backup_name="未命名备份"):
        """创建新备份
        
        Args:
            backup_name: 备份名称
            
        Returns:
            tuple: (成功标志, 消息)
        """
        if not os.path.exists(self.source_path):
            return False, "源目录不存在！"
            
        # 检查是否需要自动保存
        if self.config['features'].get('auto_save_before_backup', False):
            # 先退出游戏到主界面触发自动保存
            exit_success, exit_message = self.auto_exit_game()
            if not exit_success:
                messagebox.showwarning("警告", exit_message)

        backup_name = backup_name.strip() or "未命名备份"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = safe_filename(backup_name)
        
        try:
            # 创建备份目录
            backup_dir = os.path.join(self.backup_root, f"{safe_name}_{timestamp}")
            
            # 检查是否启用MD5去重
            use_md5 = self.config['features']['md5_deduplication']
            
            if use_md5:
                # MD5去重模式
                metadata_dir = os.path.join(backup_dir, "metadata")
                ensure_dir(metadata_dir)
                
                # 存储文件元数据信息
                file_metadata = []
                
                # 遍历源目录中的所有文件
                for root, _, files in os.walk(self.source_path):
                    for file in files:
                        src_file_path = os.path.join(root, file)
                        # 计算相对路径
                        rel_path = os.path.relpath(src_file_path, self.source_path)
                        
                        # 计算文件MD5
                        file_md5 = calculate_file_md5(src_file_path)
                        
                        # 仓库中的文件路径
                        repo_file_path = os.path.join(self.file_repository, file_md5)
                        
                        # 如果文件不在仓库中，则复制到仓库
                        if not os.path.exists(repo_file_path):
                            # 使用with语句确保文件句柄正确关闭
                            with open(src_file_path, 'rb') as src_file:
                                with open(repo_file_path, 'wb') as dest_file:
                                    dest_file.write(src_file.read())
                        
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
                # 传统模式 - 使用安全的文件复制方法
                ensure_dir(backup_dir)
                data_dir = os.path.join(backup_dir, "data")
                ensure_dir(data_dir)
                self._safe_copy_tree(self.source_path, data_dir)
                
                # 记录备份元数据
                self.backups.append({
                    "name": backup_name,
                    "date": datetime.now().isoformat(),
                    "path": backup_dir,
                    "type": "legacy"
                })
                
            self.save_backups()
            
            # 检查是否需要自动载入
            if self.config['features'].get('auto_save_before_backup', False):
                # 备份完成后自动载入
                load_success, load_message = self.auto_load_game()
                if not load_success:
                    messagebox.showwarning("警告", load_message)
            
            return True, f"备份成功：{backup_name}"
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False, f"备份失败：{str(e)}"
    
    def quick_backup(self):
        """快速备份功能
        
        Returns:
            tuple: (成功标志, 消息)
        """
        if not os.path.exists(self.source_path):
            return False, "源目录不存在"
            
        # 检查是否需要自动保存
        if self.config['features'].get('auto_save_before_backup', False):
            # 先退出游戏到主界面触发自动保存
            exit_success, exit_message = self.auto_exit_game()
            if not exit_success:
                messagebox.showwarning("警告", exit_message)

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"快速备份_{timestamp}"
            backup_dir = os.path.join(self.backup_root, f"quick_{timestamp}")
            
            # 检查是否启用MD5去重
            use_md5 = self.config['features']['md5_deduplication']
            
            if use_md5:
                # MD5去重模式
                metadata_dir = os.path.join(backup_dir, "metadata")
                ensure_dir(metadata_dir)
                
                # 存储文件元数据信息
                file_metadata = []
                
                # 遍历源目录中的所有文件
                for root, _, files in os.walk(self.source_path):
                    for file in files:
                        src_file_path = os.path.join(root, file)
                        # 计算相对路径
                        rel_path = os.path.relpath(src_file_path, self.source_path)
                        
                        # 计算文件MD5
                        file_md5 = calculate_file_md5(src_file_path)
                        
                        # 仓库中的文件路径
                        repo_file_path = os.path.join(self.file_repository, file_md5)
                        
                        # 如果文件不在仓库中，则复制到仓库
                        if not os.path.exists(repo_file_path):
                            # 使用with语句确保文件句柄正确关闭
                            with open(src_file_path, 'rb') as src_file:
                                with open(repo_file_path, 'wb') as dest_file:
                                    dest_file.write(src_file.read())
                        
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
                # 传统模式 - 使用安全的文件复制方法
                ensure_dir(backup_dir)
                data_dir = os.path.join(backup_dir, "data")
                ensure_dir(data_dir)
                self._safe_copy_tree(self.source_path, data_dir)
                
                # 记录备份元数据
                self.backups.append({
                    "name": backup_name,
                    "date": datetime.now().isoformat(),
                    "path": backup_dir,
                    "type": "legacy"
                })
                
            self.save_backups()
            
            # 检查是否需要自动载入
            if self.config['features'].get('auto_save_before_backup', False):
                # 备份完成后自动载入
                load_success, load_message = self.auto_load_game()
                if not load_success:
                    messagebox.showwarning("警告", load_message)
            
            return True, f"快速备份成功：{backup_name}"
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False, f"快速备份失败：{str(e)}"
    
    def restore_backup(self, backup_path, backup_name):
        """恢复指定备份
        
        Args:
            backup_path: 备份路径
            backup_name: 备份名称
            
        Returns:
            tuple: (成功标志, 消息)
        """
        try:
            # 检查备份路径是否存在
            if not os.path.exists(backup_path):
                return False, "备份路径不存在或无法访问"
                
            # 获取备份的详细信息
            backup_info = None
            for backup in self.backups:
                if backup["path"] == backup_path:
                    backup_info = backup
                    break
            
            if not backup_info:
                return False, "找不到备份信息"
            
            # 检查是否需要自动载入
            if self.config['features'].get('auto_load_after_restore', False):
                # 先退出游戏
                exit_success, exit_message = self.auto_exit_game()
                if not exit_success:
                    messagebox.showwarning("警告", exit_message)
            
            # 清空目标目录
            if os.path.exists(self.source_path):
                shutil.rmtree(self.source_path)
            ensure_dir(self.source_path)
            
            # 检查备份类型，处理MD5去重备份
            if backup_info.get("type") == "md5":
                metadata_file = os.path.join(backup_path, "metadata", "files.json")
                if not os.path.exists(metadata_file):
                    return False, "备份元数据文件不存在"
                
                # 加载文件元数据
                try:
                    with open(metadata_file, "r", encoding="utf-8") as f:
                        file_metadata = json.load(f)
                except json.JSONDecodeError:
                    return False, "备份元数据文件已损坏，无法解析JSON格式"
                
                # 验证元数据格式
                if not isinstance(file_metadata, list):
                    return False, "备份元数据格式错误，应为文件列表"
                
                # 根据元数据恢复文件
                corrupted_files = []
                missing_files = []
                invalid_paths = []
                
                for file_info in file_metadata:
                    # 验证文件信息完整性
                    if not all(k in file_info for k in ["path", "md5", "size", "mtime"]):
                        continue  # 跳过不完整的文件信息
                    
                    # 检查文件路径是否合法
                    if not file_info["path"] or ".." in file_info["path"] or file_info["path"].startswith("/"):
                        invalid_paths.append(file_info["path"])
                        continue
                    
                    # 目标文件路径
                    dest_file_path = os.path.join(self.source_path, file_info["path"])
                    # 确保目标目录存在
                    ensure_dir(os.path.dirname(dest_file_path))
                    
                    # 仓库中的文件路径
                    repo_file_path = os.path.join(self.file_repository, file_info["md5"])
                    
                    if os.path.exists(repo_file_path):
                        # 验证仓库中文件的完整性
                        repo_file_size = os.path.getsize(repo_file_path)
                        if repo_file_size != file_info["size"]:
                            corrupted_files.append(file_info["path"])
                            continue
                            
                        # 验证MD5哈希值
                        actual_md5 = calculate_file_md5(repo_file_path)
                        if actual_md5 != file_info["md5"]:
                            corrupted_files.append(file_info["path"])
                            continue
                            
                        # 从仓库复制文件 - 使用with语句确保文件句柄正确关闭
                        with open(repo_file_path, 'rb') as src_file:
                            with open(dest_file_path, 'wb') as dest_file:
                                dest_file.write(src_file.read())
                        # 恢复文件的修改时间
                        os.utime(dest_file_path, (file_info["mtime"], file_info["mtime"]))
                    else:
                        missing_files.append(file_info["path"])
                
                # 显示警告信息
                if corrupted_files:
                    messagebox.showwarning("警告", f"检测到{len(corrupted_files)}个文件已损坏，这些文件可能无法正常恢复")
                
                if missing_files:
                    messagebox.showwarning("警告", f"仓库中找不到{len(missing_files)}个文件")
                    
                if invalid_paths:
                    messagebox.showwarning("警告", f"检测到{len(invalid_paths)}个无效的文件路径")
                    
                if corrupted_files and len(corrupted_files) > len(file_metadata) // 2:
                    return False, "大部分备份文件已损坏，恢复操作已取消"
            else:
                # 处理旧版备份格式
                data_path = os.path.join(backup_path, "data")
                if not os.path.exists(data_path):
                    return False, "备份数据目录不存在"
                    
                # 自定义复制函数，确保文件句柄正确关闭
                self._safe_copy_tree(data_path, self.source_path)
            
            # 检查是否需要自动载入
            if self.config['features'].get('auto_load_after_restore', False):
                # 恢复存档后自动载入
                load_success, load_message = self.auto_load_game()
                if not load_success:
                    messagebox.showwarning("警告", load_message)
                
            return True, f"已从 {backup_name} 恢复存档"
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False, f"恢复失败：{str(e)}"
    
    def quick_restore(self):
        """快速恢复最新备份
        
        Returns:
            tuple: (成功标志, 消息)
        """
        if not self.backups:
            return False, "没有可用的备份"

        try:
            latest = max(self.backups, key=lambda x: x["date"])
            backup_path = latest["path"]
            
            # 检查备份路径是否存在
            if not os.path.exists(backup_path):
                return False, "最新备份路径不存在或无法访问"
            
            # 检查是否需要自动载入
            if self.config['features'].get('auto_load_after_restore', False):
                # 先退出游戏
                exit_success, exit_message = self.auto_exit_game()
                if not exit_success:
                    messagebox.showwarning("警告", exit_message)
            
            # 清空目标目录
            if os.path.exists(self.source_path):
                shutil.rmtree(self.source_path)
            ensure_dir(self.source_path)
            
            # 检查备份类型，处理MD5去重备份
            if latest.get("type") == "md5":
                metadata_file = os.path.join(backup_path, "metadata", "files.json")
                if not os.path.exists(metadata_file):
                    return False, "备份元数据文件不存在"
                
                # 加载文件元数据
                try:
                    with open(metadata_file, "r", encoding="utf-8") as f:
                        file_metadata = json.load(f)
                except json.JSONDecodeError:
                    return False, "备份元数据文件已损坏，无法解析JSON格式"
                
                # 验证元数据格式
                if not isinstance(file_metadata, list):
                    return False, "备份元数据格式错误，应为文件列表"
                
                # 根据元数据恢复文件
                corrupted_files = []
                missing_files = []
                invalid_paths = []
                
                for file_info in file_metadata:
                    # 验证文件信息完整性
                    if not all(k in file_info for k in ["path", "md5", "size", "mtime"]):
                        continue  # 跳过不完整的文件信息
                    
                    # 检查文件路径是否合法
                    if not file_info["path"] or ".." in file_info["path"] or file_info["path"].startswith("/"):
                        invalid_paths.append(file_info["path"])
                        continue
                    
                    # 目标文件路径
                    dest_file_path = os.path.join(self.source_path, file_info["path"])
                    # 确保目标目录存在
                    ensure_dir(os.path.dirname(dest_file_path))
                    
                    # 仓库中的文件路径
                    repo_file_path = os.path.join(self.file_repository, file_info["md5"])
                    
                    if os.path.exists(repo_file_path):
                        # 验证仓库中文件的完整性
                        repo_file_size = os.path.getsize(repo_file_path)
                        if repo_file_size != file_info["size"]:
                            corrupted_files.append(file_info["path"])
                            continue
                            
                        # 验证MD5哈希值
                        actual_md5 = calculate_file_md5(repo_file_path)
                        if actual_md5 != file_info["md5"]:
                            corrupted_files.append(file_info["path"])
                            continue
                            
                        # 从仓库复制文件 - 使用with语句确保文件句柄正确关闭
                        with open(repo_file_path, 'rb') as src_file:
                            with open(dest_file_path, 'wb') as dest_file:
                                dest_file.write(src_file.read())
                        # 恢复文件的修改时间
                        os.utime(dest_file_path, (file_info["mtime"], file_info["mtime"]))
                    else:
                        missing_files.append(file_info["path"])
                
                # 显示警告信息
                if corrupted_files:
                    messagebox.showwarning("警告", f"检测到{len(corrupted_files)}个文件已损坏，这些文件可能无法正常恢复")
                
                if missing_files:
                    messagebox.showwarning("警告", f"仓库中找不到{len(missing_files)}个文件")
                    
                if invalid_paths:
                    messagebox.showwarning("警告", f"检测到{len(invalid_paths)}个无效的文件路径")
                    
                if corrupted_files and len(corrupted_files) > len(file_metadata) // 2:
                    return False, "大部分备份文件已损坏，恢复操作已取消"
            else:
                # 处理旧版备份格式
                data_path = os.path.join(backup_path, "data")
                if not os.path.exists(data_path):
                    return False, "备份数据目录不存在"
                    
                # 自定义复制函数，确保文件句柄正确关闭
                self._safe_copy_tree(data_path, self.source_path)
            
            # 检查是否需要自动载入
            if self.config['features'].get('auto_load_after_restore', False):
                # 恢复存档后自动载入
                load_success, load_message = self.auto_load_game()
                if not load_success:
                    messagebox.showwarning("警告", load_message)
                
            return True, f"已快速恢复：{latest['name']}"
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False, f"快速恢复失败：{str(e)}"
    
    def delete_backup(self, backup_path, backup_name):
        """删除备份
        
        Args:
            backup_path: 备份路径
            backup_name: 备份名称
            
        Returns:
            tuple: (成功标志, 消息)
        """
        try:
            # 删除备份文件
            shutil.rmtree(backup_path)
            # 更新备份记录
            self.backups = [b for b in self.backups if b['path'] != backup_path]
            self.save_backups()
            return True, f"已删除备份：{backup_name}"
        except Exception as e:
            return False, f"删除失败：{str(e)}"
    
    def rename_backup(self, backup_path, new_name):
        """重命名备份
        
        Args:
            backup_path: 备份路径
            new_name: 新名称
            
        Returns:
            tuple: (成功标志, 消息, 旧名称)
        """
        old_name = ""
        try:
            # 更新备份记录
            for backup in self.backups:
                if backup['path'] == backup_path:
                    old_name = backup['name']
                    backup['name'] = new_name
                    break
            self.save_backups()
            return True, f"已重命名：{old_name} -> {new_name}", old_name
        except Exception as e:
            return False, f"重命名失败：{str(e)}", old_name
    
    def duplicate_backup(self, src_path, src_name):
        """复制备份
        
        Args:
            src_path: 源备份路径
            src_name: 源备份名称
            
        Returns:
            tuple: (成功标志, 消息)
        """
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
                return False, "找不到源备份信息"
                
            # 检查备份类型
            if src_backup.get("type") == "md5":
                # 创建元数据目录
                metadata_dir = os.path.join(new_path, "metadata")
                ensure_dir(metadata_dir)
                
                # 复制元数据文件
                src_metadata_file = os.path.join(src_path, "metadata", "files.json")
                if os.path.exists(src_metadata_file):
                    with open(src_metadata_file, "r", encoding="utf-8") as f:
                        file_metadata = json.load(f)
                    
                    # 保存到新备份
                    with open(os.path.join(metadata_dir, "files.json"), "w", encoding="utf-8") as f:
                        json.dump(file_metadata, f, ensure_ascii=False, indent=2)
                else:
                    return False, "源备份的元数据文件不存在"
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
            return True, f"已创建副本：{new_name}"
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False, f"创建副本失败：{str(e)}"
    
    def _safe_copy_tree(self, src, dst):
        """安全地复制目录树，确保所有文件句柄都被正确关闭
        
        Args:
            src: 源目录路径
            dst: 目标目录路径
        """
        # 确保目标目录存在
        ensure_dir(dst)
        
        # 遍历源目录
        for item in os.listdir(src):
            s = os.path.join(src, item)
            d = os.path.join(dst, item)
            
            if os.path.isdir(s):
                # 如果是目录，递归复制
                self._safe_copy_tree(s, d)
            else:
                # 如果是文件，使用with语句确保文件句柄正确关闭
                ensure_dir(os.path.dirname(d))
                with open(s, 'rb') as src_file:
                    with open(d, 'wb') as dst_file:
                        dst_file.write(src_file.read())
                # 保留文件的修改时间和访问时间
                os.utime(d, (os.path.getatime(s), os.path.getmtime(s)))
    
    def auto_exit_game(self):
        """自动退出游戏"""
        try:
            # 等待一段时间确保文件已经完全写入
            import time
            # 尝试多个可能的窗口标题
            window_titles = ["Bloodborne", "BLOODBORNE", "血源诅咒", "血源"]
            window_found = False
            
            # 多次尝试查找窗口
            max_attempts = 3
            for attempt in range(max_attempts):
                for title in window_titles:
                    if focus_window(title):
                        window_found = True
                        # 给窗口更多时间来响应
                        time.sleep(0.1)
                        break
                if window_found:
                    break
                time.sleep(0.5)  # 等待一段时间再次尝试
            
            if window_found:
                simulate_key_press('enter')
                simulate_key_press('left')
                simulate_key_press('b')
                simulate_key_press('up')
                simulate_key_press('b')
                simulate_key_press('left')
                simulate_key_press('b')
                
                return True, "已自动退出游戏"
            else:
                return False, "未找到游戏窗口"
        except Exception as e:
            return False, f"自动退出失败：{str(e)}"
        
    def auto_load_game(self):
        """自动载入游戏存档"""
        try:
            # 等待一段时间确保文件已经完全写入
            import time
            time.sleep(3.5)
            # 尝试多个可能的窗口标题
            window_titles = ["Bloodborne", "BLOODBORNE", "血源诅咒", "血源"]
            window_found = False
            
            # 多次尝试查找窗口
            max_attempts = 3
            for attempt in range(max_attempts):
                for title in window_titles:
                    if focus_window(title):
                        window_found = True
                        # 给窗口更多时间来响应
                        time.sleep(0.1)
                        break
                if window_found:
                    break
                time.sleep(0.5)  # 等待一段时间再次尝试
            
            if window_found:
                simulate_key_press('b')
                simulate_key_press('b')
                
                
                
                return True, "已自动载入存档"
            else:
                return False, "未找到游戏窗口，请手动载入存档"
        except Exception as e:
            return False, f"自动载入失败：{str(e)}"
        
    
    def calculate_storage_stats(self):
        """计算存储统计信息
        
        Returns:
            dict: 统计信息字典
        """
        if not self.backups:
            return None
            
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
            
            return {
                "backup_count": backup_count,
                "md5_backup_count": md5_backup_count,
                "repo_size": repo_size,
                "total_files": total_files,
                "theoretical_size": theoretical_size,
                "saved_space": saved_space,
                "saved_percentage": saved_percentage
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return None