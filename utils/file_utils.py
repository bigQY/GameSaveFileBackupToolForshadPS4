#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
文件工具模块 - 提供文件操作相关的工具函数
"""

import os
import hashlib
import shutil


def calculate_file_md5(file_path):
    """计算文件的MD5哈希值
    
    Args:
        file_path: 文件路径
        
    Returns:
        str: MD5哈希值的十六进制字符串
    """
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def format_size(size_bytes):
    """格式化文件大小显示
    
    Args:
        size_bytes: 文件大小（字节）
        
    Returns:
        str: 格式化后的大小字符串，如 "1.23 MB"
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024 or unit == 'GB':
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024


def ensure_dir(directory):
    """确保目录存在，如果不存在则创建
    
    Args:
        directory: 目录路径
    """
    os.makedirs(directory, exist_ok=True)


def safe_filename(filename):
    """生成安全的文件名，移除不允许的字符
    
    Args:
        filename: 原始文件名
        
    Returns:
        str: 安全的文件名
    """
    return "".join([c for c in filename if c not in r'\/:*?"<>|'])