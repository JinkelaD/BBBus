"""Tkinter 集成热键 — 键盘轮询 + 鼠标低层钩子。

键盘热键：GetAsyncKeyState 轮询，不依赖 RegisterHotKey，在远程桌面/沙箱中也能工作。
鼠标热键（侧键 mb4/mb5、滚轮 wheel_up/wheel_down）：用 WH_MOUSE_LL 低层钩子全局捕获。
原因：XButton 与滚轮事件无法用 GetAsyncKeyState 可靠检测（微软文档明确不返回滚轮状态）。

【关键稳定性说明】
低层鼠标钩子的回调，必须在「拥有消息循环、且持有完整 Python 线程状态」的线程中被调用。
若把钩子装在 Tkinter 主线程——其主消息循环是 Tcl 事件循环，跑事件时会释放 GIL、
把当前线程的 Python 线程状态置为 NULL——回调在 Tcl 事件循环内被分发时，ctypes 的 GIL
进出处理会与「线程状态为 NULL」冲突；若回调内再调用 tkinter（如 root.after）造成重入，
就会触发 Fatal Python error: PyEval_RestoreThread (thread state is NULL)。

本实现把低层钩子安装到「专用 Python 线程」，该线程自带消息循环
（PeekMessage/TranslateMessage/DispatchMessage），回调在完整 Python 线程状态下执行；
回调内「绝不调用 tkinter」，只置位一个线程安全标志（threading.Event），
再由主线程的 after 轮询消费并触发用户回调（在主线程安全执行）。
"""

__author__ = "Jinkela"

import ctypes
import ctypes.wintypes
import threading
import time

from vk_map import VK_MAP, MOD_MAP, MOD_FLAGS, MOUSE_MAP
from logger import log

user32 = ctypes.windll.user32

# ── 低层鼠标钩子常量 ──
WH_MOUSE_LL = 14
WM_XBUTTONDOWN = 0x020B
WM_MOUSEWHEEL = 0x020A
XBUTTON1 = 0x0001
XBUTTON2 = 0x0002
PM_REMOVE = 0x0001
PM_NOREMOVE = 0x0000


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", POINT),
        ("mouseData", ctypes.wintypes.DWORD),
        ("flags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


# LowLevelMouseProc 签名: (nCode:int, wParam:WPARAM, lParam:LPARAM) -> LRESULT
# 返回类型用 c_longlong（64 位 LRESULT），避免 64 位平台上返回值被截断。
HOOKPROC = ctypes.WINFUNCTYPE(
    ctypes.c_longlong,
    ctypes.c_int,
    ctypes.c_void_p,
    ctypes.c_void_p,
)

# 当前活动的鼠标热键管理器（供模块级钩子回调访问，避免在闭包里保存 self 造成引用问题）
_MOUSE_MGR_REF = None


def _mouse_hook_proc_global(n_code, w_param, l_param):
    """模块级低层鼠标钩子回调。

    只做最小化的事件判定并置位标志，**绝不调用 tkinter**（否则会重入 Tk）。
    """
    mgr = _MOUSE_MGR_REF
    if mgr is not None and n_code >= 0:
        try:
            mgr._on_mouse_event(w_param, l_param)
        except Exception as exc:
            log(f"鼠标钩子事件处理异常: {exc}")
    return user32.CallNextHookEx(None, n_code, w_param, l_param)


# 模块级保存引用，防止回调对象被 GC 回收
_LL_MOUSE_PROC = HOOKPROC(_mouse_hook_proc_global)


# ── 声明 argtypes / restype（关键）──
# 若不声明，ctypes 默认把参数当 32 位 c_int，会把 64 位句柄（如 hMod）截断成无效值，
# 导致 SetWindowsHookExW 静默失败（返回 NULL）。此处按真实原型声明。
user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int,                  # idHook
    HOOKPROC,                      # lpfn
    ctypes.wintypes.HINSTANCE,     # hMod（低层钩子必须传 NULL）
    ctypes.wintypes.DWORD,         # dwThreadId
]
user32.SetWindowsHookExW.restype = ctypes.wintypes.HHOOK

user32.CallNextHookEx.argtypes = [
    ctypes.wintypes.HHOOK, ctypes.c_int,
    ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM,
]
user32.CallNextHookEx.restype = ctypes.c_longlong

user32.UnhookWindowsHookEx.argtypes = [ctypes.wintypes.HHOOK]
user32.UnhookWindowsHookEx.restype = ctypes.wintypes.BOOL

user32.PeekMessageW.argtypes = [
    ctypes.POINTER(ctypes.wintypes.MSG), ctypes.wintypes.HWND,
    ctypes.wintypes.UINT, ctypes.wintypes.UINT, ctypes.wintypes.UINT,
]
user32.PeekMessageW.restype = ctypes.wintypes.BOOL

user32.TranslateMessage.argtypes = [ctypes.POINTER(ctypes.wintypes.MSG)]
user32.TranslateMessage.restype = ctypes.wintypes.BOOL

user32.DispatchMessageW.argtypes = [ctypes.POINTER(ctypes.wintypes.MSG)]
user32.DispatchMessageW.restype = ctypes.c_longlong


def parse_hotkey(hotkey_str: str) -> tuple[int, int, "str | None"]:
    """解析热键字符串。返回 (mod_flags, vk_or_code, mouse_kind)。

    mouse_kind: None（键盘）/ "xbtn"（鼠标侧键）/ "wheel"（滚轮）。
    vk_or_code: 键盘为 VK 码；xbtn 为 XBUTTON1/2；wheel 为 +1/-1。
    """
    parts = [p.strip().lower() for p in hotkey_str.split("+")]
    mod, vk, mouse_kind = 0, 0, None
    for p in parts:
        if p in MOD_MAP:
            mod |= MOD_MAP[p]
        elif p in VK_MAP:
            vk = VK_MAP[p]
        elif p in MOUSE_MAP:
            mouse_kind, code = MOUSE_MAP[p]
            vk = code
        else:
            raise ValueError(f"无法识别的热键部分: {p}")
    if vk == 0:
        raise ValueError(f"热键缺少按键: {hotkey_str}")
    return mod, vk, mouse_kind


class TkHotkeyManager:
    """Tkinter 集成热键管理器（单热键，支持键盘与鼠标）。

    键盘：GetAsyncKeyState 主线程轮询。
    鼠标：WH_MOUSE_LL 钩子，装在专用线程，回调仅置标志，主线程轮询触发。
    """

    def __init__(self, root):
        self._root = root
        self._hotkey_str = ""
        self._mod_flags = 0
        self._vk = 0
        self._mouse_kind = None       # None | "xbtn" | "wheel"
        self._mouse_code = 0          # xbtn: XBUTTON1/2；wheel: +1/-1
        self._callback = None
        self._active = False
        self._poll_id = None
        self._was_pressed = False
        self._pending = threading.Event()        # 钩子线程置位，主线程消费
        self._last_mouse_trigger = 0.0
        self._stop_ev = threading.Event()
        self._hook_thread = None
        self._hook_id = None

    def register(self, hotkey_str: str, callback: callable) -> bool:
        """注册热键。返回是否成功解析。"""
        if not hotkey_str.strip():
            return False
        try:
            mod, vk, mouse_kind = parse_hotkey(hotkey_str)
        except ValueError:
            return False
        self._hotkey_str = hotkey_str
        self._mod_flags = mod
        self._vk = vk
        self._mouse_kind = mouse_kind
        self._mouse_code = vk if mouse_kind is not None else 0
        self._callback = callback
        self._was_pressed = False
        self._last_mouse_trigger = 0.0
        return True

    def start(self):
        if self._active:
            return
        self._active = True
        self._was_pressed = False
        self._last_mouse_trigger = 0.0
        self._pending.clear()
        self._stop_ev.clear()
        if self._mouse_kind is not None:
            # 鼠标热键：在专用线程安装低层钩子（避免卡死主线程）
            self._hook_thread = threading.Thread(
                target=self._mouse_loop, daemon=True)
            self._hook_thread.start()
        # 主线程轮询（键盘检测 + 消费鼠标 pending）
        self._poll()

    def _mouse_loop(self):
        global _MOUSE_MGR_REF
        _MOUSE_MGR_REF = self
        # 关键：先让本线程拥有消息队列。刚启动的线程尚未泵过消息，
        # 没有消息队列；低层钩子要求安装线程能接收钩子消息，否则安装必失败。
        dummy = ctypes.wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(dummy), 0, 0, 0, PM_NOREMOVE)
        # 低层鼠标钩子的 hMod 必须传 NULL（回调在“安装线程”本进程内执行，无需 DLL 句柄）。
        # 若传 64 位模块句柄且未声明 argtypes，会被 ctypes 默认截断为无效值而失败。
        hook = user32.SetWindowsHookExW(WH_MOUSE_LL, _LL_MOUSE_PROC, None, 0)
        if not hook:
            err = ctypes.GetLastError()
            print(f"[BBBus] 鼠标热键钩子安装失败 (code={err})，鼠标热键将不可用")
            # 侧键可回退到 GetAsyncKeyState 检测；滚轮无回退方案
            if self._mouse_kind == "xbtn":
                self._vk = 0x05 if self._mouse_code == XBUTTON1 else 0x06
                self._mouse_kind = None
            return
        self._hook_id = hook
        msg = ctypes.wintypes.MSG()
        # 低层钩子要求线程泵消息；PeekMessage 循环即可触发回调
        while not self._stop_ev.is_set():
            if user32.PeekMessageW(ctypes.byref(msg), 0, 0, 0, PM_REMOVE):
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            else:
                time.sleep(0.005)
        try:
            user32.UnhookWindowsHookEx(hook)
        except Exception:
            pass
        self._hook_id = None

    def _on_mouse_event(self, w_param, l_param):
        """在钩子线程中执行：只判定事件、置位标志，绝不调用 tkinter。"""
        if not self._active:
            return
        # 修饰键检查（仅查询物理状态，不涉及 tkinter）
        for flag, vk_mod in MOD_FLAGS:
            if self._mod_flags & flag:
                if not (user32.GetAsyncKeyState(vk_mod) & 0x8000):
                    return
        if self._mouse_kind == "xbtn":
            if w_param != WM_XBUTTONDOWN:
                return
            struct = ctypes.cast(l_param, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
            xbtn = (struct.mouseData >> 16) & 0xFFFF
            if xbtn != self._mouse_code:
                return
            self._pending.set()
        elif self._mouse_kind == "wheel":
            if w_param != WM_MOUSEWHEEL:
                return
            struct = ctypes.cast(l_param, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
            delta = ctypes.c_short((struct.mouseData >> 16) & 0xFFFF).value
            if (self._mouse_code == 1 and delta <= 0) or \
               (self._mouse_code == -1 and delta >= 0):
                return
            self._pending.set()

    def _trigger(self):
        try:
            if self._callback:
                self._callback()
        except Exception as exc:
            log(f"热键回调异常: {exc}")

    def _poll(self):
        if not self._active:
            return
        try:
            if self._mouse_kind is not None:
                # 鼠标：消费钩子线程置位的标志，带去抖
                if self._pending.is_set():
                    self._pending.clear()
                    now = time.time()
                    debounce = 0.2 if self._mouse_kind == "xbtn" else 0.3
                    if now - self._last_mouse_trigger >= debounce:
                        self._last_mouse_trigger = now
                        self._trigger()
            elif self._vk:
                # 键盘：GetAsyncKeyState 边沿检测
                mods_ok = True
                for flag, vk_mod in MOD_FLAGS:
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
                        self._trigger()
                    elif not key_down:
                        self._was_pressed = False
        except Exception as exc:
            log(f"热键轮询异常: {exc}")
        finally:
            # 无论本次是否异常，都继续轮询（避免单次异常永久停摆热键）
            if self._active:
                try:
                    self._poll_id = self._root.after(30, self._poll)
                except Exception:
                    pass

    def stop(self):
        self._active = False
        self._stop_ev.set()
        if self._hook_thread is not None:
            self._hook_thread.join(timeout=1.0)
            self._hook_thread = None
        if self._hook_id:
            try:
                user32.UnhookWindowsHookEx(self._hook_id)
            except Exception:
                pass
            self._hook_id = None
        global _MOUSE_MGR_REF
        if _MOUSE_MGR_REF is self:
            _MOUSE_MGR_REF = None
        if self._poll_id:
            try:
                self._root.after_cancel(self._poll_id)
            except Exception:
                pass
            self._poll_id = None
        self._pending.clear()
        self._hotkey_str = ""
        self._vk = 0
        self._mouse_kind = None
        self._mouse_code = 0
        self._callback = None
        self._was_pressed = False
