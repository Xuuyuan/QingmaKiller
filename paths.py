"""程序目录定位: 兼容 PyInstaller 打包(frozen)与源码运行两种场景"""
import os
import sys


def get_app_dir():  # 获取程序所在目录(打包为exe后为exe所在目录)
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))
