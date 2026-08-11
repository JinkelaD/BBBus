"""按键工作线程 — 单目标按键循环。"""

__author__ = "Jinkela"

import random
import threading
import time
import ctypes

import psutil

from vk_map import VK_MAP
from logger import log

# 进程列表缓存
_proc_cache = {"time": 0.0, "data": {}}
_PROC_CACHE_TTL = 2.0

# 窗口句柄缓存
_hwnd_cache = {}
_HWND_CACHE_TTL = 5.0


def _get_vk(key_name: str) -> int:
    key = key_name.lower().strip()
    vk = VK_MAP.get(key)
    if vk is not None:
        return vk
    raise ValueError(f"不支持的按键: {key_name}")


def _find_window_by_process(name: str, pid: int = 0):
    target_name = name.lower().strip()
    now = time.time()
    cache_key = pid if pid else target_name

    cached = _hwnd_cache.get(cache_key)
    if cached and now - cached[1] < _HWND_CACHE_TTL:
        hwnd = cached[0]
        user32 = ctypes.windll.user32
        if user32.IsWindow(hwnd) and user32.IsWindowVisible(hwnd):
            c_pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(c_pid))
            if pid != 0:
                if c_pid.value == pid:
                    return hwnd
            else:
                try:
                    if psutil.Process(c_pid.value).name().lower() == target_name:
                        return hwnd
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        del _hwnd_cache[cache_key]

    match_pids = None
    if pid == 0:
        proc_cache = get_running_processes()
        match_pids = set()
        for pname, pids in proc_cache.items():
            if pname.lower() == target_name:
                match_pids.update(pids)
        if not match_pids:
            return None

    user32 = ctypes.windll.user32
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
    result = {"hwnd": None}

    def enum_proc(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        c_pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(c_pid))
        if pid != 0:
            if c_pid.value == pid:
                result["hwnd"] = hwnd
                return False
        elif match_pids and c_pid.value in match_pids:
            result["hwnd"] = hwnd
            return False
        return True

    user32.EnumWindows(WNDENUMPROC(enum_proc), 0)

    if result["hwnd"] is not None:
        _hwnd_cache[cache_key] = (result["hwnd"], now)
    return result["hwnd"]


def _send_key_to_window(hwnd, vk: int, hold_ms: int = 5) -> float:
    """发送按键，返回实际耗时 ms。"""
    t0 = time.perf_counter()
    user32 = ctypes.windll.user32
    WM_KEYDOWN = 0x0100
    WM_KEYUP = 0x0101
    sc = user32.MapVirtualKeyW(vk, 0)

    def _lp(repeat=1, sc=0, ext=False, ctx=0, prev=0, trans=0):
        return (repeat | (sc << 16) | (1 << 24 if ext else 0)
                | (ctx << 29) | (prev << 30) | (trans << 31))

    user32.PostMessageW(hwnd, WM_KEYDOWN, vk, _lp(sc=sc))
    time.sleep(hold_ms / 1000.0)
    user32.PostMessageW(hwnd, WM_KEYUP, vk, _lp(sc=sc, prev=1, trans=1))
    return (time.perf_counter() - t0) * 1000.0


def key_press_loop(
    stop_event: threading.Event,
    config_lock: threading.Lock,
    shared_config: dict,
) -> None:
    last_sub_send = 0.0  # 上次发送副键的时间戳（time.time()）
    while not stop_event.is_set():
        with config_lock:
            cfg = shared_config.copy()

        name = cfg.get("name", "").strip()
        pid = cfg.get("pid", 0)
        target_key = cfg.get("target_key", "f1")
        interval_min = cfg.get("interval_min", 50)
        interval_max = cfg.get("interval_max", 950)
        sub_key = cfg.get("sub_key", "").strip()
        sub_key_interval = cfg.get("sub_key_interval", 5000)

        if not name:
            stop_event.wait(0.5)
            continue

        hwnd = _find_window_by_process(name, pid)
        if hwnd is None:
            stop_event.wait(0.5)
            continue

        try:
            vk = _get_vk(target_key)
        except ValueError:
            stop_event.wait(0.5)
            continue

        # 副按键逻辑：若已启用且距上次副键发送超过间隔，则发送副键
        now = time.time()
        if sub_key and (now - last_sub_send) * 1000 >= sub_key_interval:
            try:
                sub_vk = _get_vk(sub_key)
                _send_key_to_window(hwnd, sub_vk)
                log(f"已向目标进程 {name} 发送副键 {sub_key}")
                last_sub_send = now
            except ValueError:
                pass  # 副键无效，跳过
        else:
            _send_key_to_window(hwnd, vk)
            log(f"已向目标进程 {name} 发送 {target_key}")

        delay_ms = random.randint(interval_min, interval_max)
        stop_event.wait(delay_ms / 1000.0)


def get_running_processes(refresh: bool = False) -> dict:
    now = time.time()
    if not refresh and now - _proc_cache["time"] < _PROC_CACHE_TTL:
        return _proc_cache["data"]
    result = {}
    for proc in psutil.process_iter(["name", "pid"]):
        try:
            name = proc.info["name"]
            pid = proc.info["pid"]
            result.setdefault(name, []).append(pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    _proc_cache["time"] = now
    _proc_cache["data"] = result
    return result
