#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
配置管理模块 - 负责处理应用程序配置
"""

import os
import json
from tkinter import messagebox


class ConfigManager:
    """配置管理类，负责加载和保存配置"""
    
    def __init__(self, config_file="config.json"):
        """初始化配置管理器
        
        Args:
            config_file: 配置文件路径
        """
        self.config_file = config_file
        self.config = self.load_config()
        
        # 初始化路径
        self.source_path = self.config['paths']['source_path']
        self.backup_root = os.path.join(os.getcwd(), self.config['paths']['backup_root'])
    
    def load_config(self):
        """加载配置文件
        
        Returns:
            dict: 配置字典
        """
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                # 默认配置
                default_config = {
                    'hotkeys': {'quick_backup': 'f7', 'quick_restore': 'f8'},
                    'paths': {
                        'source_path': r"D:\games\shadPS4\user\savedata\1\CUSA03023\SPRJ0005",
                        'backup_root': 'backups'
                    },
                    'features': {
                        'md5_deduplication': True,
                        'auto_load_after_restore': False
                    }
                }
                self.save_config(default_config)
                return default_config
        except Exception as e:
            messagebox.showerror("错误", f"加载配置文件失败：{str(e)}")
            # 返回默认配置
            return {
                'hotkeys': {'quick_backup': 'f7', 'quick_restore': 'f8'},
                'paths': {
                    'source_path': r"D:\games\shadPS4\user\savedata\1\CUSA03023\SPRJ0005",
                    'backup_root': 'backups'
                },
                'features': {
                    'md5_deduplication': True,
                    'auto_load_after_restore': False
                }
            }
    
    def save_config(self, config=None):
        """保存配置文件
        
        Args:
            config: 要保存的配置，默认为当前配置
        """
        if config is None:
            config = self.config
            
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            messagebox.showerror("错误", f"保存配置文件失败：{str(e)}")
    
    def update_config(self, new_config):
        """更新配置
        
        Args:
            new_config: 新的配置字典
        """
        self.config = new_config
        self.source_path = self.config['paths']['source_path']
        self.backup_root = os.path.join(os.getcwd(), self.config['paths']['backup_root'])
        self.save_config()
    
    def get_config(self):
        """获取当前配置
        
        Returns:
            dict: 当前配置字典
        """
        return self.config