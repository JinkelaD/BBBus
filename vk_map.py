"""公共按键映射 — 按键名 → 虚拟键码 (VK)。

供 hotkey_manager 与 key_worker 共用。
"""

__author__ = "Jinkela"

# ── 修饰键 VK ──
VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_MENU = 0x12    # Alt
VK_LWIN = 0x5B

# ── 修饰键名 → 修饰键标志位 ──
MOD_MAP = {
    "alt": 0x0001, "ctrl": 0x0002, "shift": 0x0004, "win": 0x0008,
    "<alt>": 0x0001, "<ctrl>": 0x0002, "<shift>": 0x0004, "<win>": 0x0008,
}

# ── 按键名 → 虚拟键码映射 ──
VK_MAP = {
    "a": 0x41, "b": 0x42, "c": 0x43, "d": 0x44, "e": 0x45, "f": 0x46,
    "g": 0x47, "h": 0x48, "i": 0x49, "j": 0x4A, "k": 0x4B, "l": 0x4C,
    "m": 0x4D, "n": 0x4E, "o": 0x4F, "p": 0x50, "q": 0x51, "r": 0x52,
    "s": 0x53, "t": 0x54, "u": 0x55, "v": 0x56, "w": 0x57, "x": 0x58,
    "y": 0x59, "z": 0x5A,
    "0": 0x30, "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34,
    "5": 0x35, "6": 0x36, "7": 0x37, "8": 0x38, "9": 0x39,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
    "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
    "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
    "space": 0x20, "enter": 0x0D, "tab": 0x09, "esc": 0x1B,
    "backspace": 0x08, "delete": 0x2E, "insert": 0x2D,
    "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
}

# ── 鼠标按键名 → (类型, 标识) ──
#   xbtn : 鼠标侧键（标识为 XBUTTON1=0x0001 / XBUTTON2=0x0002，取自钩子 mouseData 高字）
#   wheel: 鼠标滚轮（dir=+1 上滚 / -1 下滚）
# 说明：键盘可用 GetAsyncKeyState 轮询；鼠标侧键与滚轮无法用其可靠检测，
#       需在 hotkey_manager 中改用 WH_MOUSE_LL 低层鼠标钩子捕获。
MOUSE_MAP = {
    "mb4": ("xbtn", 0x0001),   # 鼠标侧键1（前进键）
    "mb5": ("xbtn", 0x0002),   # 鼠标侧键2（后退键）
    "wheel_up": ("wheel", 1),  # 滚轮上滚
    "wheel_down": ("wheel", -1),  # 滚轮下滚
}

# 修饰键标志位 → VK 映射
_MOD_FLAGS = [
    (0x0002, VK_CONTROL),  # ctrl
    (0x0004, VK_SHIFT),    # shift
    (0x0001, VK_MENU),     # alt
    (0x0008, VK_LWIN),     # win
]
