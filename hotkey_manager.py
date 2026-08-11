"""Tkinter 集成热键 — GetAsyncKeyState 轮询方案（单热键）。

不依赖 RegisterHotKey / 消息钩子，直接轮询按键物理状态。
在沙箱/远程终端环境中也能工作。
"""

__author__ = "Jinkela"

import ctypes
import ctypes.wintypes

from vk_map import VK_MAP, MOD_MAP, _MOD_FLAGS

user32 = ctypes.windll.user32


def parse_hotkey(hotkey_str: str) -> tuple[int, int]:
    parts = [p.strip().lower() for p in hotkey_str.split("+")]
    mod, vk = 0, 0
    for p in parts:
        if p in MOD_MAP:
            mod |= MOD_MAP[p]
        elif p in VK_MAP:
            vk = VK_MAP[p]
        else:
            raise ValueError(f"无法识别的热键部分: {p}")
    if vk == 0:
        raise ValueError(f"热键缺少按键: {hotkey_str}")
    return mod, vk


class TkHotkeyManager:
    """Tkinter 集成热键管理器（单热键）。

    通过 GetAsyncKeyState 轮询检测热键组合，不依赖系统热键注册。
    """

    def __init__(self, root):
        self._root = root
        self._hotkey_str = ""
        self._mod_flags = 0
        self._vk = 0
        self._callback = None
        self._active = False
        self._poll_id = None
        self._was_pressed = False

    def register(self, hotkey_str: str, callback: callable) -> bool:
        """注册热键。返回是否成功。"""
        if not hotkey_str.strip():
            return False
        try:
            mod, vk = parse_hotkey(hotkey_str)
        except ValueError:
            return False
        self._hotkey_str = hotkey_str
        self._mod_flags = mod
        self._vk = vk
        self._callback = callback
        self._was_pressed = False
        return True

    def start(self):
        if self._active:
            return
        self._active = True
        self._was_pressed = False
        self._poll()

    def _poll(self):
        if not self._active:
            return

        if self._vk == 0:
            self._poll_id = self._root.after(100, self._poll)
            return

        mods_ok = True
        for flag, vk_mod in _MOD_FLAGS:
            if self._mod_flags & flag:
                if not (user32.GetAsyncKeyState(vk_mod) & 0x8000):
                    mods_ok = False
                    break

        if not mods_ok:
            self._was_pressed = False
        else:
            key_down = bool(user32.GetAsyncKeyState(self._vk) & 0x8000)
            if key_down and not self._was_pressed:
                self._was_pressed = True
                try:
                    if self._callback:
                        self._callback()
                except Exception:
                    pass
            elif not key_down:
                self._was_pressed = False

        self._poll_id = self._root.after(100, self._poll)

    def stop(self):
        self._active = False
        if self._poll_id:
            self._root.after_cancel(self._poll_id)
            self._poll_id = None
        self._hotkey_str = ""
        self._vk = 0
        self._callback = None
        self._was_pressed = False
