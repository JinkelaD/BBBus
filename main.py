"""BBBus Tool — Windows 自动化按键工具入口。"""

__author__ = "Jinkela"

import ctypes
import sys
import tkinter as tk
from gui import BBBusApp


def main():
    # 必须在创建窗口之前设置 AppUserModelID，否则任务栏图标不生效
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Jinkela.BBBus")
            # 启用高 DPI 感知，避免 UI 模糊/像素感
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    root = tk.Tk()
    BBBusApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
