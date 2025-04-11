#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
i18n模块 - 国际化支持
提供多语言翻译和语言切换功能
"""

from pathlib import Path
import json
import locale

class I18nManager:
    _instance = None
    _current_lang = None
    _translations = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._current_lang:
            self._init_translations()
    
    def _init_translations(self):
        """初始化翻译资源"""
        # 使用系统默认语言作为初始语言
        system_lang = locale.getdefaultlocale()[0]
        self._current_lang = 'zh_CN' if system_lang.startswith('zh') else 'en_US'
        
        # 加载翻译文件
        i18n_dir = Path(__file__).parent / 'locales'
        for lang_file in i18n_dir.glob('*.json'):
            lang_code = lang_file.stem
            with open(lang_file, 'r', encoding='utf-8') as f:
                self._translations[lang_code] = json.load(f)
    
    def get_text(self, key, lang=None):
        """获取指定键的翻译文本"""
        lang = lang or self._current_lang
        try:
            return self._translations[lang][key]
        except KeyError:
            return key
    
    def set_language(self, lang_code):
        """设置当前语言"""
        if lang_code in self._translations:
            self._current_lang = lang_code
            return True
        return False
    
    def get_current_language(self):
        """获取当前语言代码"""
        return self._current_lang
    
    def get_available_languages(self):
        """获取所有可用的语言代码"""
        return list(self._translations.keys())

# 创建全局访问点
def get_i18n_manager():
    return I18nManager()

# 便捷翻译函数
def t(key):
    return get_i18n_manager().get_text(key)