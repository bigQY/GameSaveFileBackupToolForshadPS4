#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
系统工具模块 - 提供进程检测、热键管理等系统相关功能
"""

import psutil
import keyboard
import win32gui
import win32con
import time

# 导入PyDirectInput库用于更可靠的游戏按键模拟
try:
    import pydirectinput
    pydirectinput.PAUSE = 0.1  # 设置按键间隔，避免按键过快
    HAS_PYDIRECTINPUT = True
except ImportError:
    HAS_PYDIRECTINPUT = False
    print("警告: PyDirectInput库未安装，将使用keyboard库作为备选方案")
    print("建议安装PyDirectInput以获得更好的游戏兼容性: pip install pydirectinput")


def is_process_running(process_name):
    """检查指定进程是否在运行
    
    Args:
        process_name: 进程名称，如 'shadPS4.exe'
        
    Returns:
        bool: 进程是否在运行
    """
    try:
        return any(p.info['name'] == process_name 
                  for p in psutil.process_iter(['name']))
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def register_hotkey(key, callback, check_process=None):
    """注册热键
    
    Args:
        key: 热键字符串，如 'f7'
        callback: 热键触发时的回调函数
        check_process: 可选，检查进程是否在运行的函数
        
    Returns:
        function: 热键注销函数
    """
    if check_process:
        def wrapper():
            if check_process():
                callback()
        keyboard.add_hotkey(key, wrapper)
    else:
        keyboard.add_hotkey(key, callback)
    
    # 返回注销函数
    return lambda: keyboard.remove_hotkey(key)


def unregister_all_hotkeys():
    """注销所有热键"""
    keyboard.unhook_all_hotkeys()


def focus_window(window_title):
    """查找并激活指定标题的窗口
    
    Args:
        window_title: 窗口标题
        
    Returns:
        bool: 是否成功激活窗口
    """
    hwnd = win32gui.FindWindow(None, window_title)
    if hwnd:
        win32gui.SetForegroundWindow(hwnd)
        return True
    return False


def simulate_key_press(key, delay=0.05):
    """模拟按键
    
    Args:
        key: 按键名称
        delay: 按键前后的延迟时间（秒）
    """
    time.sleep(delay)
    
    # 优先使用PyDirectInput库，它更适合游戏输入
    if HAS_PYDIRECTINPUT:
        try:
            pydirectinput.press(key)
        except Exception as e:
            print(f"PyDirectInput按键失败: {str(e)}，尝试使用keyboard库")
            keyboard.press_and_release(key)
    else:
        # 备选方案：使用keyboard库
        keyboard.press_and_release(key)
        
    time.sleep(delay)