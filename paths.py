"""路径解析工具 — 统一获取程序基目录（兼容 PyInstaller 打包）。

原先 config.py / logger.py / gui.py 各自重复实现
`getattr(sys, "frozen", False)` + `os.path.dirname` 的路径判定逻辑；
统一收敛到本模块，避免三处不同步（见优化建议 P3-2）。
"""

__author__ = "Jinkela"

import os
import sys


def get_base_path() -> str:
    """返回程序基目录：打包后为 exe 所在目录，否则为源码目录。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))
