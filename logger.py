"""日志模块 — 写入 BBBus.log（线程安全，句柄常驻）。

优化点（相较旧版）：
  · 句柄常驻：旧版每次 log() 都 open/close 文件，50ms 间隔下每秒 20 次
    文件开关，对磁盘 IO 与元数据有明显开销（P1-5）。现改为启用时打开、
    禁用或退出时关闭，写操作只 append + flush。
  · 写入失败降级：旧版 open()/write() 抛异常会直接传播到工作线程，
    导致按键循环崩溃（P1-6）。现捕获 OSError 静默降级，保证主功能不中断。
  · 路径解析收敛到 paths.get_base_path（P3-2）。
"""

__author__ = "Jinkela"

import os
import sys
import threading
from datetime import datetime

from paths import get_base_path

LOG_PATH = os.path.join(get_base_path(), "BBBus.log")

_log_lock = threading.Lock()  # 线程安全写入
_log_enabled = False          # 日志开关，默认关闭
_log_file = None              # 常驻文件句柄（启用时打开）


def set_enabled(enable: bool) -> None:
    """启用或禁用日志写入（启用时打开句柄，禁用时关闭）。"""
    global _log_enabled, _log_file
    with _log_lock:
        if enable == _log_enabled:
            return
        _log_enabled = enable
        if enable:
            try:
                _log_file = open(LOG_PATH, "a", encoding="utf-8")
            except OSError:
                # 打开失败：保持禁用，后续写入自动跳过
                _log_file = None
        else:
            if _log_file is not None:
                try:
                    _log_file.close()
                except OSError:
                    pass
                _log_file = None


def log(msg: str) -> None:
    """写入一行日志，格式：YYYY-MM-DD HH:MM:SS.mmm | 消息。

    写入失败（磁盘满 / 权限不足等）时静默降级，绝不抛出异常，
    以免拖垮调用方（尤其是按键工作线程）。
    """
    if not _log_enabled:
        return
    now = datetime.now()
    ts = now.strftime("%Y-%m-%d %H:%M:%S") + f".{now.microsecond // 1000:03d}"
    line = f"{ts} | {msg}\n"
    with _log_lock:
        if _log_file is None:
            return
        try:
            _log_file.write(line)
            _log_file.flush()
        except OSError:
            pass


def close_log() -> None:
    """显式关闭日志句柄（程序退出时调用）。"""
    global _log_file
    with _log_lock:
        if _log_file is not None:
            try:
                _log_file.close()
            except OSError:
                pass
            _log_file = None
