"""配置管理模块 — 单目标进程配置。

优化点（相较旧版）：
  · to_dict 改用 dataclasses.asdict，from_dict 改为按字段自举，
    新增字段只需改 @dataclass 一处，消除三处不同步（P2-2）。
  · 新增 version 字段 + CONFIG_VERSION，为后续配置迁移留出扩展点（P2-7）。
  · 配置损坏时备份原文件并记录告警，不再静默回退（P2-3）。
  · save_config 采用「临时文件 + os.replace」原子写，避免写入被中断产生半截文件。
  · 路径解析收敛到 paths.get_base_path（P3-2）。
"""

__author__ = "Jinkela"

import json
import os
import shutil
import sys
from dataclasses import dataclass, asdict, fields

from paths import get_base_path

CONFIG_PATH = os.path.join(get_base_path(), "config.json")

CONFIG_VERSION = 1


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
    version: int = CONFIG_VERSION

    def to_dict(self) -> dict:
        # 由 dataclass 自动生成，新增字段无需手动维护
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "AppConfig":
        if not isinstance(d, dict):
            d = {}
        valid = {f.name for f in fields(AppConfig)}
        kwargs = {k: d[k] for k in valid if k in d}
        cfg = AppConfig(**kwargs)
        cfg.version = d.get("version", CONFIG_VERSION)
        return cfg


def load_config() -> AppConfig:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            return AppConfig.from_dict(data)
        except (json.JSONDecodeError, KeyError) as exc:
            # JSON 结构错误：按损坏处理
            _backup_corrupt(exc)
        except OSError as exc:
            # 文件无法读取（权限等）：仅告警，回退默认
            print(f"[BBBus] 配置文件读取失败，使用默认配置：{exc}")
    return AppConfig()


def _backup_corrupt(exc) -> None:
    """配置损坏时备份原文件，避免无声丢失用户数据。"""
    bak = CONFIG_PATH + ".corrupt.bak"
    try:
        shutil.copy2(CONFIG_PATH, bak)
        bak_msg = bak
    except OSError:
        bak_msg = "(备份失败)"
    print(f"[BBBus] 配置文件已损坏，已备份至 {bak_msg}，回退默认配置。原因：{exc}")


def save_config(cfg: AppConfig) -> None:
    cfg.version = CONFIG_VERSION
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg.to_dict(), f, ensure_ascii=False, indent=2)
    # 原子替换：要么旧文件、要么新文件完整存在，避免中断产生半截 config.json
    os.replace(tmp, CONFIG_PATH)
