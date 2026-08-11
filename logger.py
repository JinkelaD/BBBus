"""日志模块 — 写入 BBBus.log（时间精确到 ms）。"""

__author__ = "Jinkela"

import os
import sys
import threading
from datetime import datetime

# 日志文件路径（与 main.py / exe 同级目录）
if getattr(sys, "frozen", False):
    LOG_PATH = os.path.join(os.path.dirname(sys.executable), "BBBus.log")
else:
    LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "BBBus.log")

_log_lock = threading.Lock()  # 线程安全写入
_log_enabled = False           # 日志开关，默认关闭


def set_enabled(enable: bool) -> None:
    """启用或禁用日志写入。"""
    global _log_enabled
    _log_enabled = enable


def log(msg: str) -> None:
    """写入一行日志，格式：YYYY-MM-DD HH:MM:SS.mmm | 消息。"""
    if not _log_enabled:
        return
    now = datetime.now()
    ts = now.strftime("%Y-%m-%d %H:%M:%S") + f".{now.microsecond // 1000:03d}"
    line = f"{ts} | {msg}\n"
    with _log_lock:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)
