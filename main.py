"""BBBus Tool — Windows 自动化按键工具入口。"""

__author__ = "Jinkela"

import ctypes
import sys
import tkinter as tk
from gui import BBBusApp


def _enable_dpi_awareness() -> None:
    """启用高 DPI 感知（P3-8）。

    Windows 10 1703+ 推荐使用 SetProcessDpiAwarenessContext(-4)
    （PROCESS_SYSTEM_DPI_AWARE）；旧系统回退到已弃用的 SetProcessDpiAwareness(1)。
    任一失败都给出明确告警，不再静默吞掉（P3-7）。
    """
    try:
        ctypes.windll.shcore.SetProcessDpiAwarenessContext(-4)
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception as exc:
            print(f"[BBBus] 高 DPI 感知初始化失败，UI 可能偏模糊：{exc}")


def main():
    # 必须在创建窗口之前设置 AppUserModelID，否则任务栏图标不生效
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "Jinkela.BBBus")
        except Exception:
            pass
        _enable_dpi_awareness()

    root = tk.Tk()
    BBBusApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
