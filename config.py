"""配置管理模块 — 单目标进程配置。"""

__author__ = "Jinkela"

import json
import os
import sys
from dataclasses import dataclass

# PyInstaller 打包后，config.json 应放在 exe 同目录下
if getattr(sys, "frozen", False):
    CONFIG_PATH = os.path.join(os.path.dirname(sys.executable), "config.json")
else:
    CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")


@dataclass
class AppConfig:
    name: str = ""             # 进程名
    pid: int = 0               # 进程 PID（0=自动匹配）
    target_key: str = "f1"     # 目标按键
    interval_min: int = 50     # 最小间隔 ms
    interval_max: int = 950    # 最大间隔 ms
    sub_key: str = ""           # 副输出按键（空=禁用）
    sub_key_interval: int = 5000  # 副键发送间隔 ms
    hotkey: str = "ctrl+shift+k"
    topmost: bool = False
    log_enabled: bool = False    # 日志开关

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "pid": self.pid,
            "target_key": self.target_key,
            "interval_min": self.interval_min,
            "interval_max": self.interval_max,
            "sub_key": self.sub_key,
            "sub_key_interval": self.sub_key_interval,
            "hotkey": self.hotkey,
            "topmost": self.topmost,
            "log_enabled": self.log_enabled,
        }

    @staticmethod
    def from_dict(d: dict) -> "AppConfig":
        return AppConfig(
            name=d.get("name", ""),
            pid=d.get("pid", 0),
            target_key=d.get("target_key", "f1"),
            interval_min=d.get("interval_min", 50),
            interval_max=d.get("interval_max", 950),
            sub_key=d.get("sub_key", ""),
            sub_key_interval=d.get("sub_key_interval", 5000),
            hotkey=d.get("hotkey", "ctrl+shift+k"),
            topmost=d.get("topmost", False),
            log_enabled=d.get("log_enabled", False),
        )


def load_config() -> AppConfig:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            return AppConfig.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            pass
    return AppConfig()


def save_config(cfg: AppConfig) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg.to_dict(), f, ensure_ascii=False, indent=2)
