"""BBBus GUI — 精密工具风格 · 全中文 · Canvas 绘制 · 紧凑布局。"""

__author__ = "Jinkela"

# ── 标准库 ──
import ctypes          # Windows API（瞄准镜、AppUserModelID）
import os              # 拼接图标文件路径
import sys             # 判断是否为 PyInstaller 打包环境
import threading       # Lock 保护 shared_config、Event 控制线程启停、Thread 运行按键循环
import tkinter as tk   # GUI 主框架
from tkinter import ttk, messagebox  # ttk 组件（Treeview 用）、消息弹窗

# ── 项目内部模块 ──
from config import load_config, save_config, AppConfig
from hotkey_manager import TkHotkeyManager
from key_worker import key_press_loop, get_running_processes
from logger import log, set_enabled

# ═══════════════════════════════════════════════════════════════
#  配色常量 — 浅色主题
# ═══════════════════════════════════════════════════════════════
LIGHT_BG         = "#f2f2f7"   # 窗口背景
LIGHT_SURFACE    = "#ffffff"   # 卡片/输入框背景
LIGHT_SURFACE_HV = "#f0f0f5"   # 卡片悬停
LIGHT_BORDER     = "#d9d9e0"   # 边框
LIGHT_TEXT       = "#1d1d1f"   # 主文字
LIGHT_TEXT_SEC   = "#6e6e73"   # 次要文字（白底对比度 ~4.6:1，满足 AA）
LIGHT_TEXT_MUTED = "#8e8e93"   # 禁用文字（白底对比度 ~3.0:1，浅色下可辨）
LIGHT_ACCENT     = "#6c8cff"   # 强调蓝（聚焦/开关激活）
LIGHT_ACCENT_DIM = "#e0e4ff"   # 强调蓝低透明度
LIGHT_GREEN      = "#3dd68c"   # 启动/成功
LIGHT_GREEN_DIM  = "#e0faf0"   # 绿色低透明度
LIGHT_RED        = "#ff5c5c"   # 停止/危险
LIGHT_RED_DIM    = "#ffe5e5"   # 红色低透明度
LIGHT_INPUT_BG   = "#f5f5fa"   # 输入框内部背景
LIGHT_INPUT_FOC  = "#ffffff"   # 输入框聚焦背景


CARD_R = 12                     # 卡片圆角半径
BTN_ACTIVE_DARKEN = 0.16        # 按钮按下变暗系数

# ═══════════════════════════════════════════════════════════════
#  字体常量
# ═══════════════════════════════════════════════════════════════
FONT_TITLE  = ("Segoe UI", 14, "bold")          # 顶部标题 (~18px @96dpi)
FONT_H2     = ("Microsoft YaHei UI", 9, "bold") # 卡片标题（小大写风格）
FONT_MAIN   = ("Microsoft YaHei UI", 10)         # 正文/对话框
FONT_BOLD   = ("Microsoft YaHei UI", 10, "bold") # 按钮
FONT_MONO   = ("Consolas", 10)                   # 等宽（输入值）
FONT_SMALL  = ("Microsoft YaHei UI", 9)          # 标签


def _darken(h: str, a: float) -> str:
    """将十六进制颜色变暗，a 为比例（0~1）。"""
    h = h.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"#{max(0,int(r*(1-a))):02x}{max(0,int(g*(1-a))):02x}{max(0,int(b*(1-a))):02x}"


# ═══════════════════════════════════════════════════════════════
#  Canvas 圆角矩形绘制
# ═══════════════════════════════════════════════════════════════
def _round_rect(cv, x1, y1, x2, y2, r, fill="", outline="", width=1, tags=None):
    """在 Canvas 上绘制圆角矩形。"""
    ids, d = [], 2 * r
    kw = {"tags": tags} if tags else {}
    for sx, sy, ex, ey, s in [
        (x1, y1, x1+d, y1+d, 90),
        (x2-d, y1, x2, y1+d, 0),
        (x2-d, y2-d, x2, y2, 270),
        (x1, y2-d, x1+d, y2, 180),
    ]:
        ids.append(cv.create_arc(sx, sy, ex, ey, start=s, extent=90,
                                  fill=fill, outline=outline, width=width, **kw))
    ids.append(cv.create_rectangle(x1+r, y1, x2-r, y2, fill=fill, outline="", **kw))
    ids.append(cv.create_rectangle(x1, y1+r, x2, y2-r, fill=fill, outline="", **kw))
    if outline:
        for lx1, ly1, lx2, ly2 in [
            (x1+r, y1, x2-r, y1),
            (x1+r, y2, x2-r, y2),
            (x1, y1+r, x1, y2-r),
            (x2, y1+r, x2, y2-r),
        ]:
            ids.append(cv.create_line(lx1, ly1, lx2, ly2,
                                       fill=outline, width=width, **kw))
    return ids


# ═══════════════════════════════════════════════════════════════
#  药丸形按钮（Canvas 实现）
# ═══════════════════════════════════════════════════════════════
def _pill_btn(cv, x, y, w, h, text, fill, text_fill="#FFFFFF",
              font=None, cmd=None, tags=None):
    """在 Canvas 上绘制药丸形按钮。"""
    internal = f"pill_{id(cv)}_{x}_{y}"
    all_tags = (internal,) if tags is None else (internal, tags)
    r = h // 2
    state = {"base": fill}

    ids = _round_rect(cv, x, y, x + w, y + h, r, fill=fill, outline="",
                      width=0, tags=all_tags)
    ids.append(cv.create_text(x + w // 2, y + h // 2, text=text,
                               fill=text_fill,
                               font=font or FONT_BOLD,
                               tags=all_tags))

    def _f(c):
        for i in cv.find_withtag(internal):
            if cv.type(i) in ("arc", "rectangle", "line"):
                cv.itemconfig(i, fill=c)

    for i in ids:
        cv.tag_bind(i, "<Enter>",          lambda _: _f(_darken(state["base"], 0.10)))
        cv.tag_bind(i, "<Leave>",          lambda _: _f(state["base"]))
        cv.tag_bind(i, "<ButtonPress-1>",  lambda _: _f(_darken(state["base"], BTN_ACTIVE_DARKEN)))
        cv.tag_bind(i, "<ButtonRelease-1>",
                    lambda _: (_f(state["base"]), cmd and cmd()))
    return ids, internal


# ═══════════════════════════════════════════════════════════════
#  滑动开关（Canvas 实现）— 模拟 Web 端的 pill toggle
# ═══════════════════════════════════════════════════════════════
class _Toggle(tk.Canvas):
    """Canvas 绘制的 pill 滑动开关，带文字标签，可点击切换。"""

    W, H = 28, 16           # 开关本体尺寸
    R = H // 2              # 圆角半径 = 半高 → 药丸形
    KNOB_R = 6              # 滑块半径
    LABEL_W = 24            # 文字预留宽度

    def __init__(self, parent, text: str, initial: bool = False, command=None):
        total_w = self.W + 4 + self.LABEL_W
        super().__init__(parent, width=total_w, height=self.H + 4,
                         bg=LIGHT_BG, highlightthickness=0)
        self._on = initial
        self._command = command

        # 文字标签（开关右侧，垂直居中）
        self._label = self.create_text(self.W + 4, self.H // 2 + 2,
                                        text=text, anchor="w",
                                        fill=LIGHT_TEXT_SEC, font=FONT_SMALL)
        # 开关轨道
        self._track = _round_rect(self, 1, 2, self.W - 1, self.H + 2,
                                   self.R, fill=LIGHT_BORDER, outline="", width=0)
        # 滑块
        kx = self.W - self.KNOB_R - 2 if self._on else self.KNOB_R + 2
        self._knob = self.create_oval(kx - self.KNOB_R, self.H // 2 + 2 - self.KNOB_R,
                                       kx + self.KNOB_R, self.H // 2 + 2 + self.KNOB_R,
                                       fill="#FFFFFF", outline="")
        self._update_colors()

        # 点击开关轨道或滑块时切换
        for item in self._track + [self._knob]:
            self.tag_bind(item, "<Button-1>", self._toggle)

        # 文字标签也可点击
        self.tag_bind(self._label, "<Button-1>", self._toggle)

        # hover 高亮文字
        self.tag_bind(self._label, "<Enter>", lambda _: self.itemconfig(self._label, fill=LIGHT_TEXT))
        self.tag_bind(self._label, "<Leave>", lambda _: self.itemconfig(self._label, fill=LIGHT_TEXT_SEC))

    def is_on(self) -> bool:
        return self._on

    def set_on(self, val: bool):
        self._on = val
        self._update_colors()

    def _toggle(self, _event=None):
        self._on = not self._on
        self._update_colors()
        if self._command:
            self._command(self._on)

    def _update_colors(self):
        """更新开关颜色 + 滑块位置。"""
        track_color = LIGHT_ACCENT if self._on else LIGHT_BORDER
        for i in self._track:
            if self.type(i) in ("arc", "rectangle", "line"):
                self.itemconfig(i, fill=track_color)
        self.itemconfig(self._label,
                        fill=LIGHT_ACCENT if self._on else LIGHT_TEXT_SEC)

        # 滑块目标位置：OFF 在左，ON 在右（从左到右）
        kx = self.W - self.KNOB_R - 2 if self._on else self.KNOB_R + 2
        cy = self.H // 2 + 2
        self.coords(self._knob,
                     kx - self.KNOB_R, cy - self.KNOB_R,
                     kx + self.KNOB_R, cy + self.KNOB_R)


# ═══════════════════════════════════════════════════════════════
#  BBBusApp — 主应用类
# ═══════════════════════════════════════════════════════════════
class BBBusApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("BBBus")
        self.root.configure(bg=LIGHT_BG)
        self.root.resizable(False, False)
        self.root.geometry("280x560")

        self._set_app_icon()

        # ── 线程安全 ──
        self.config_lock = threading.Lock()
        self.shared_config: dict = {}
        self.stop_event = threading.Event()
        self.stop_event.set()
        self.worker_thread = None
        self.running = False

        self.hotkey_mgr = TkHotkeyManager(self.root)

        # ── 占位符追踪 ──
        self._ph_vars: dict = {}

        cfg = load_config()
        self._cfg_to_shared(cfg)
        self._build_ui()
        self._load_to_ui(cfg)
        self.root.update()
        self._resize_all()

    # ═══════════════════════════════════════════════════════════
    #  应用图标
    # ═══════════════════════════════════════════════════════════
    def _set_app_icon(self):
        if getattr(sys, 'frozen', False):
            base = sys._MEIPASS
        else:
            base = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(base, "icon", "bbbus_icon.ico")
        if os.path.exists(icon_path):
            self.root.iconbitmap(icon_path)

    # ═══════════════════════════════════════════════════════════
    #  配置同步
    # ═══════════════════════════════════════════════════════════
    def _cfg_to_shared(self, cfg: AppConfig):
        with self.config_lock:
            self.shared_config = cfg.to_dict()

    # ═══════════════════════════════════════════════════════════
    #  UI 构建
    # ═══════════════════════════════════════════════════════════
    def _build_ui(self):
        """构建全部界面组件 —— 顶部栏 → 配置卡片 → 按钮 → 状态栏。"""
        px = 18

        # ═══════════ 顶部栏：标题 + 开关 ═══════════
        top = tk.Frame(self.root, bg=LIGHT_BG)
        top.pack(fill=tk.X, padx=px, pady=(16, 0))

        # 标题 "BBBus"，BB 白色 + Bus 强调蓝
        title_frame = tk.Frame(top, bg=LIGHT_BG)
        title_frame.pack(side=tk.LEFT)
        tk.Label(title_frame, text="BB", bg=LIGHT_BG, fg=LIGHT_TEXT,
                 font=FONT_TITLE).pack(side=tk.LEFT)
        tk.Label(title_frame, text="Bus", bg=LIGHT_BG, fg=LIGHT_ACCENT,
                 font=FONT_TITLE).pack(side=tk.LEFT)

        # 开关组：日志 + 置顶
        toggles = tk.Frame(top, bg=LIGHT_BG)
        toggles.pack(side=tk.RIGHT)

        self.log_toggle = _Toggle(toggles, "日志", initial=False,
                                   command=self._toggle_log)
        self.log_toggle.pack(side=tk.LEFT, padx=(0, 10))

        self.topmost_toggle = _Toggle(toggles, "置顶", initial=True,
                                       command=self._toggle_topmost)
        self.topmost_toggle.pack(side=tk.LEFT)

        # ═══════════ 配置卡片 Canvas ═══════════
        self.cfg_canvas = tk.Canvas(self.root, bg=LIGHT_BG, highlightthickness=0)
        self.cfg_canvas.pack(fill=tk.X, padx=px, pady=(14, 6))
        self.root.bind("<Configure>", self._on_resize, add="+")

        self.cfg_frame = tk.Frame(self.cfg_canvas, bg=LIGHT_SURFACE)
        self.cfg_frame.place(x=0, y=0)

        # ═══════════ 卡片标题行 ═══════════
        hdr = tk.Frame(self.cfg_frame, bg=LIGHT_SURFACE)
        hdr.pack(fill=tk.X, padx=14, pady=(14, 10))

        title_lbl = tk.Label(hdr, text="目标配置", bg=LIGHT_SURFACE, fg=LIGHT_TEXT_SEC,
                             font=FONT_H2)
        title_lbl.pack(side=tk.LEFT)

        btn_spacer = tk.Frame(hdr, bg=LIGHT_SURFACE, height=1)
        btn_spacer.pack(side=tk.LEFT, expand=True, fill=tk.X)

        # 图标按钮 — 自定义 Canvas 绘制，暗色风格
        self.btn_browse = self._mk_icon_btn(hdr, "☰", self._browse_process)
        self.btn_browse.pack(side=tk.LEFT)
        self.btn_target = self._mk_icon_btn(hdr, "⊙", self._target_window)
        self.btn_target.pack(side=tk.LEFT, padx=(6, 0))

        # ═══════════ 表单区域 ═══════════
        form = tk.Frame(self.cfg_frame, bg=LIGHT_SURFACE)
        form.pack(anchor=tk.W, padx=14, pady=(0, 8))

        lbl_w = 7

        def _row(label_text):
            r = tk.Frame(form, bg=LIGHT_SURFACE)
            r.pack(fill=tk.X, pady=4)
            lbl = tk.Label(r, text=label_text, bg=LIGHT_SURFACE, fg=LIGHT_TEXT_MUTED,
                           font=FONT_SMALL, width=lbl_w, anchor=tk.W)
            lbl.pack(side=tk.LEFT)
            self._row_lbl = lbl
            return r

        def _sep():
            s = tk.Frame(form, bg=LIGHT_SURFACE)
            s.pack(fill=tk.X, pady=(4, 3))
            tk.Frame(s, bg=LIGHT_BORDER, height=1).pack(fill=tk.X)

        # 1) 进程名称
        rp = _row("进程名称")
        self.name_var = tk.StringVar()
        self._mk_entry(rp, self.name_var, "notepad.exe").pack(side=tk.LEFT, padx=(4, 0))

        # 2) PID
        rpid = _row("PID")
        self.pid_var = tk.StringVar()
        pe = self._mk_entry(rpid, self.pid_var, "自动检测")
        pe.pack(side=tk.LEFT, padx=(4, 0))
        pid_entry = pe._entry
        pid_entry.bind("<FocusOut>", self._on_pid_focusout)
        pid_entry.bind("<Return>", self._on_pid_focusout)

        # 3) 输出按键
        rk = _row("输出按键")
        self.key_var = tk.StringVar()
        self._mk_entry(rk, self.key_var, "f1").pack(side=tk.LEFT, padx=(4, 0))

        # 4) 间隔下限
        rmin = _row("间隔下限")
        self.min_var = tk.StringVar()
        self._mk_entry(rmin, self.min_var, "ms").pack(side=tk.LEFT, padx=(4, 0))

        # 5) 间隔上限
        rmax = _row("间隔上限")
        self.max_var = tk.StringVar()
        self._mk_entry(rmax, self.max_var, "ms").pack(side=tk.LEFT, padx=(4, 0))

        # 分隔线
        _sep()

        # 6) 副输出按键
        rsk = _row("副输出键")
        self.sub_key_var = tk.StringVar()
        self._mk_entry(rsk, self.sub_key_var, "空=禁用").pack(side=tk.LEFT, padx=(4, 0))

        # 7) 副键间隔
        rsi = _row("副键间隔")
        self.sub_interval_var = tk.StringVar()
        self._mk_entry(rsi, self.sub_interval_var, "ms").pack(side=tk.LEFT, padx=(4, 0))

        # 分隔线
        _sep()

        # 8) 快速热键
        rh = _row("快速热键")
        self.hotkey_var = tk.StringVar()
        self._mk_entry(rh, self.hotkey_var, "ctrl+shift+k").pack(side=tk.LEFT, padx=(4, 0))

        # ═══════════ 按钮区域（Canvas 绘制药丸按钮） ═══════════
        self.btn_canvas = tk.Canvas(self.root, bg=LIGHT_BG, highlightthickness=0)
        self.btn_canvas.pack(fill=tk.X, padx=px, pady=(0, 4))

        # ═══════════ 状态栏 ═══════════
        status_frame = tk.Frame(self.root, bg=LIGHT_BG)
        status_frame.pack(fill=tk.X, padx=px, pady=(0, 10))
        self.status_dot_canvas = tk.Canvas(status_frame, width=6, height=6,
                                            bg=LIGHT_BG, highlightthickness=0)
        self.status_dot_canvas.pack(side=tk.LEFT, padx=(0, 4))
        self._status_dot = self.status_dot_canvas.create_oval(0, 0, 6, 6,
                                                               fill=LIGHT_BORDER, outline="")
        self.status_label = tk.Label(status_frame, text="待命中", bg=LIGHT_BG,
                                      fg=LIGHT_TEXT_MUTED, font=FONT_SMALL)
        self.status_label.pack(side=tk.LEFT)

        # ═══════════ 关闭协议 ═══════════
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _mk_entry(self, parent, var, placeholder=""):
        """创建暗色主题输入框容器（圆角感知边框，固定宽度 120px）。"""
        # 用 Frame 背景色模拟 1px 边框（比 highlightthickness 更平滑）
        f = tk.Frame(parent, bg=LIGHT_BORDER, width=120, height=30)
        f.pack_propagate(False)

        inner = tk.Frame(f, bg=LIGHT_INPUT_BG)
        inner.pack(padx=1, pady=1, fill=tk.BOTH, expand=True)

        e = tk.Entry(inner, textvariable=var,
                     bg=LIGHT_INPUT_BG, fg=LIGHT_TEXT,
                     insertbackground=LIGHT_ACCENT, insertwidth=1,
                     font=FONT_MONO,
                     relief="flat", borderwidth=0)
        e.pack(fill=tk.BOTH, expand=True, padx=9, pady=3)

        def _on_focus_in(ev):
            f.config(bg=LIGHT_ACCENT)

        def _on_focus_out(ev):
            f.config(bg=LIGHT_BORDER)

        if placeholder:
            ph_showing = [not bool(var.get())]
            self._ph_vars[str(var)] = placeholder

            def _show_ph():
                if not var.get():
                    var.set(placeholder)
                    e.config(fg=LIGHT_TEXT_MUTED)
                    ph_showing[0] = True

            def _hide_ph():
                if ph_showing[0]:
                    var.set("")
                    e.config(fg=LIGHT_TEXT)
                    ph_showing[0] = False

            if ph_showing[0]:
                var.set(placeholder)
                e.config(fg=LIGHT_TEXT_MUTED)

            # 跟踪外部写入（如进程对话框设置 PID），自动清除占位符状态
            def _on_var_write(*_):
                if ph_showing[0] and var.get() != placeholder:
                    ph_showing[0] = False
                    e.config(fg=LIGHT_TEXT)
            var.trace_add("write", _on_var_write)

            e.bind("<FocusIn>",  lambda ev: (_on_focus_in(ev), _hide_ph()))
            e.bind("<FocusOut>", lambda ev: (_on_focus_out(ev), _show_ph()))

            def _on_keypress(ev):
                if ph_showing[0]:
                    var.set("")
                    e.config(fg=LIGHT_TEXT)
                    ph_showing[0] = False
            e.bind("<Key>", _on_keypress)
        else:
            e.bind("<FocusIn>",  _on_focus_in)
            e.bind("<FocusOut>", _on_focus_out)

        # 保存引用以便外部绑定
        f._entry = e
        return f

    def _mk_icon_btn(self, parent, text, cmd):
        """创建 Canvas 绘制的圆角图标按钮（26×26，模拟 Web 风格）。"""
        SIZE = 26
        RADIUS = 6
        cv = tk.Canvas(parent, width=SIZE, height=SIZE,
                       bg=LIGHT_SURFACE, highlightthickness=0, cursor="hand2")

        def _draw(fill, outline, text_fill):
            cv.delete("all")
            _round_rect(cv, 1, 1, SIZE - 1, SIZE - 1, RADIUS,
                        fill=fill, outline=outline, width=1)
            cv.create_text(SIZE // 2, SIZE // 2, text=text,
                           fill=text_fill, font=("Segoe UI", 11))

        def _draw_default():
            _draw(LIGHT_SURFACE, LIGHT_BORDER, LIGHT_TEXT_SEC)

        def _draw_hover():
            _draw(LIGHT_SURFACE_HV, LIGHT_TEXT_MUTED, LIGHT_TEXT)

        _draw_default()

        cv.bind("<Enter>", lambda _: _draw_hover())
        cv.bind("<Leave>", lambda _: _draw_default())
        cv.bind("<Button-1>", lambda _: cmd())

        # 按下缩放效果
        def _press(e):
            cv.scale("all", SIZE // 2, SIZE // 2, 0.92, 0.92)
        def _release(e):
            cv.scale("all", SIZE // 2, SIZE // 2, 1 / 0.92, 1 / 0.92)
        cv.bind("<ButtonPress-1>", _press, add="+")
        cv.bind("<ButtonRelease-1>", _release, add="+")
        return cv

    # ═══════════════════════════════════════════════════════════
    #  PID 自动回填
    # ═══════════════════════════════════════════════════════════
    def _on_pid_focusout(self, event=None):
        import psutil
        pid_str = self.pid_var.get().strip()
        if not pid_str:
            return
        try:
            pid = int(pid_str)
        except ValueError:
            return
        try:
            name = psutil.Process(pid).name()
            self.name_var.set(name)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    # ═══════════════════════════════════════════════════════════
    #  尺寸计算 & Canvas 重绘
    # ═══════════════════════════════════════════════════════════
    def _resize_all(self):
        self.root.update_idletasks()
        w = self.root.winfo_width() - 36  # 窗口宽 − 两侧 padding

        content_h = self.cfg_frame.winfo_reqheight()
        pill_h, pill_margin = 36, 6
        card_h = content_h + 2

        self.cfg_canvas.config(height=card_h)
        self.cfg_canvas.delete("__card__", "__btn__")

        # 卡片主体
        _round_rect(self.cfg_canvas, 0, 0, w, card_h, CARD_R,
                    fill=LIGHT_SURFACE, outline=LIGHT_BORDER, width=1, tags="__card__")
        self.cfg_frame.place(x=0, y=0, width=w, height=content_h)

        # ── 药丸按钮：启动 / 停止 ──
        bw, bh, gap = 92, pill_h, 12
        btn_y = pill_margin
        total_btn_w = bw * 2 + gap
        x_center = w // 2
        x_start = x_center - total_btn_w // 2
        x_stop = x_start + bw + gap

        if self.running:
            start_fill, start_txt = LIGHT_SURFACE, LIGHT_TEXT_SEC
            stop_fill, stop_txt = LIGHT_RED, "#FFFFFF"
        else:
            start_fill, start_txt = LIGHT_GREEN, "#FFFFFF"
            stop_fill, stop_txt = LIGHT_SURFACE, LIGHT_TEXT_SEC

        # 停止按钮（右侧）
        _pill_btn(self.btn_canvas, x_stop, btn_y, bw, bh,
                  "停止", stop_fill, text_fill=stop_txt, font=FONT_BOLD,
                  cmd=self._stop, tags="__btn__")
        # 启动按钮（左侧）
        _pill_btn(self.btn_canvas, x_start, btn_y, bw, bh,
                  "启动", start_fill, text_fill=start_txt, font=FONT_BOLD,
                  cmd=self._start, tags="__btn__")

        self.btn_canvas.config(height=pill_h + pill_margin * 2)

        # 状态灯
        if self.running:
            self.status_dot_canvas.itemconfig(self._status_dot, fill=LIGHT_GREEN)
            name = self.name_var.get().strip() or "?"
            key = self.key_var.get().strip() or "?"
            self.status_label.config(text=f"运行中 — {name} · {key}", fg=LIGHT_TEXT_SEC)
        else:
            self.status_dot_canvas.itemconfig(self._status_dot, fill=LIGHT_BORDER)
            self.status_label.config(text="待命中", fg=LIGHT_TEXT_MUTED)

    def _on_resize(self, ev):
        if ev.widget == self.root:
            self._resize_all()

    # ═══════════════════════════════════════════════════════════
    #  配置 IO
    # ═══════════════════════════════════════════════════════════
    def _load_to_ui(self, cfg: AppConfig):
        self.topmost_toggle.set_on(cfg.topmost)
        self.log_toggle.set_on(cfg.log_enabled)
        set_enabled(cfg.log_enabled)
        self.name_var.set(cfg.name)
        self.pid_var.set(str(cfg.pid) if cfg.pid else "")
        self.key_var.set(cfg.target_key)
        self.min_var.set(str(cfg.interval_min))
        self.max_var.set(str(cfg.interval_max))
        self.sub_key_var.set(cfg.sub_key)
        self.sub_interval_var.set(str(cfg.sub_key_interval))
        self.hotkey_var.set(cfg.hotkey)
        if cfg.topmost:
            self.root.attributes("-topmost", True)
            self._start_hotkey()

    def _parse_int(self, s: str, default: int = 50) -> int:
        try:
            return int(s.strip())
        except ValueError:
            return default

    def _collect_config(self) -> dict:
        """收集当前 UI 配置（过滤占位符）。"""
        def _val(var, default=""):
            v = var.get().strip()
            ph = self._ph_vars.get(str(var), "")
            return default if ph and v == ph else v

        pid_str = _val(self.pid_var)
        try:
            pid = int(pid_str) if pid_str else 0
        except ValueError:
            pid = 0
        return {
            "name": _val(self.name_var),
            "pid": pid,
            "target_key": _val(self.key_var),
            "interval_min": self._parse_int(_val(self.min_var), 50),
            "interval_max": self._parse_int(_val(self.max_var), 950),
            "sub_key": _val(self.sub_key_var),
            "sub_key_interval": self._parse_int(_val(self.sub_interval_var), 5000),
            "hotkey": _val(self.hotkey_var),
            "topmost": self.topmost_toggle.is_on(),
            "log_enabled": self.log_toggle.is_on(),
        }

    def _save_config(self):
        d = self._collect_config()
        with self.config_lock:
            self.shared_config = d
        cfg = AppConfig(**{k: v for k, v in d.items() if k not in ("topmost", "log_enabled")})
        cfg.topmost = d["topmost"]
        cfg.log_enabled = d["log_enabled"]
        save_config(cfg)

    # ═══════════════════════════════════════════════════════════
    #  瞄准镜
    # ═══════════════════════════════════════════════════════════
    def _target_window(self):
        import psutil
        u = ctypes.windll.user32
        GR = 2

        self.root.withdraw()
        self.root.update()

        ss = 72
        sc = tk.Toplevel(self.root)
        sc.overrideredirect(True)
        sc.attributes("-topmost", True, "-alpha", 0.85)
        sc.configure(bg=LIGHT_BG)
        sc.geometry(f"{ss}x{ss}")
        sc.config(cursor="crosshair")

        cv = tk.Canvas(sc, width=ss, height=ss, bg=LIGHT_BG, highlightthickness=0)
        cv.pack()
        cx = ss // 2
        cv.create_oval(8, 8, ss - 8, ss - 8, outline=LIGHT_ACCENT, width=2)
        g = 10
        cv.create_line(g, cx, cx - 6, cx, fill=LIGHT_ACCENT, width=1)
        cv.create_line(cx + 6, cx, ss - g, cx, fill=LIGHT_ACCENT, width=1)
        cv.create_line(cx, g, cx, cx - 6, fill=LIGHT_ACCENT, width=1)
        cv.create_line(cx, cx + 6, cx, ss - g, fill=LIGHT_ACCENT, width=1)
        cv.create_oval(cx - 2, cx - 2, cx + 2, cx + 2, fill=LIGHT_ACCENT, outline="")

        R = {"done": False, "name": "", "pid": 0}

        def fol():
            if R["done"]:
                return
            pt = ctypes.wintypes.POINT()
            u.GetCursorPos(ctypes.byref(pt))
            sc.geometry(f"+{pt.x - ss//2}+{pt.y - ss//2}")
            sc.after(16, fol)

        def clk(_):
            if R["done"]: return
            R["done"] = True
            sc.withdraw(); self.root.update()
            pt = ctypes.wintypes.POINT()
            u.GetCursorPos(ctypes.byref(pt))
            sc.geometry("+99999+99999"); sc.update()
            hw = u.WindowFromPoint(pt.x, pt.y)
            if hw:
                hw = u.GetAncestor(hw, GR)
                cp = ctypes.c_ulong()
                u.GetWindowThreadProcessId(hw, ctypes.byref(cp))
                pv = cp.value
                try:
                    R["name"] = psutil.Process(pv).name() if pv else ""
                except:
                    R["name"] = ""
                R["pid"] = pv
            sc.destroy(); self.root.deiconify(); self.root.lift()
            if R["name"]:
                self.name_var.set(R["name"])
                self.pid_var.set(str(R["pid"]))

        def cn(_):
            R["done"] = True; sc.destroy()
            self.root.deiconify(); self.root.lift()

        sc.bind("<Button-1>", clk)
        sc.bind("<Escape>", cn); sc.bind("<Button-3>", cn)
        fol()

    # ═══════════════════════════════════════════════════════════
    #  进程浏览对话框
    # ═══════════════════════════════════════════════════════════
    def _browse_process(self):
        r = self._show_process_dialog()
        if r:
            self.name_var.set(r["name"])
            self.pid_var.set(str(r["pid"]) if r["pid"] else "")

    def _show_process_dialog(self):
        win = tk.Toplevel(self.root)
        win.title("选择进程")
        win.geometry("420x380")
        win.configure(bg=LIGHT_SURFACE)
        win.transient(self.root)
        win.grab_set()
        result = {"value": None}

        tk.Label(win, text="搜索进程", bg=LIGHT_SURFACE, fg=LIGHT_TEXT,
                 font=FONT_H2).pack(padx=14, pady=(12, 4), anchor=tk.W)

        sv = tk.StringVar()
        sf = tk.Frame(win, bg=LIGHT_BORDER)
        sf.pack(fill=tk.X, padx=14, pady=(0, 6))
        sfi = tk.Frame(sf, bg=LIGHT_INPUT_BG)
        sfi.pack(padx=1, pady=1, fill=tk.BOTH, expand=True)
        se = tk.Entry(sfi, textvariable=sv, bg=LIGHT_INPUT_BG, fg=LIGHT_TEXT,
                      insertbackground=LIGHT_ACCENT, font=FONT_MAIN,
                      relief="flat", borderwidth=0)
        se.pack(ipady=2, padx=6, pady=3)
        se.bind("<FocusIn>",  lambda e: sf.config(bg=LIGHT_ACCENT))
        se.bind("<FocusOut>", lambda e: sf.config(bg=LIGHT_BORDER))

        tf = tk.Frame(win, bg=LIGHT_SURFACE)
        tf.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 6))
        tree = ttk.Treeview(tf, columns=("pid",), show="tree headings",
                            selectmode="browse")
        tree.heading("#0", text=" 进程名称")
        tree.heading("pid", text=" PID")
        tree.column("#0", width=200, stretch=True)
        tree.column("pid", width=70, stretch=False, anchor=tk.E)

        st = ttk.Style()
        st.theme_use("clam")  # 支持完整自定义配色
        st.configure("Treeview", background=LIGHT_SURFACE, foreground=LIGHT_TEXT,
                     fieldbackground=LIGHT_SURFACE, borderwidth=0,
                     font=FONT_MAIN)
        st.map("Treeview", background=[("selected", LIGHT_ACCENT_DIM)],
               foreground=[("selected", LIGHT_ACCENT)])
        st.configure("Treeview.Heading", background=LIGHT_BG,
                     foreground=LIGHT_TEXT_SEC,
                     font=FONT_BOLD, borderwidth=0)
        # 滚动条
        st.configure("Vertical.TScrollbar", background=LIGHT_SURFACE,
                     troughcolor=LIGHT_BG, bordercolor=LIGHT_BORDER,
                     arrowcolor=LIGHT_TEXT_SEC)
        # 底部按钮
        st.configure("TButton", background=LIGHT_SURFACE, foreground=LIGHT_TEXT,
                     font=FONT_BOLD, borderwidth=1, bordercolor=LIGHT_BORDER)
        st.map("TButton", background=[("active", LIGHT_SURFACE_HV)])

        sb = ttk.Scrollbar(tf, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        procs = get_running_processes()
        all_items = []
        info = {}
        for name in sorted(procs.keys()):
            pids = procs[name]
            if len(pids) == 1:
                it = tree.insert("", tk.END, text=f" {name}", values=(f" {pids[0]}",))
                all_items.append((it, name, pids[0]))
                info[it] = (name, pids[0])
            else:
                parent = tree.insert("", tk.END, text=f" {name}", open=False)
                all_items.append((parent, name, 0))
                info[parent] = (name, pids[0])
                for p in pids:
                    child = tree.insert(parent, tk.END, values=(f" {p}",))
                    all_items.append((child, name, p))
                    info[child] = (name, p)

        def on_s(*_):
            q = sv.get().lower()
            vis = set()
            for it, nm, pid in all_items:
                tree.detach(it)
                if q in nm.lower() or q in str(pid):
                    vis.add(it)
                    p = tree.parent(it)
                    if p:
                        vis.add(p)
            for it, nm, pid in all_items:
                if it in vis:
                    tree.reattach(it, tree.parent(it) or "", tk.END)

        sv.trace_add("write", on_s)

        def do_sel():
            s = tree.selection()
            if not s:
                messagebox.showwarning("提示", "请先选择一个进程", parent=win)
                return False
            nm, pid = info.get(s[0], ("", 0))
            if not nm:
                messagebox.showwarning("提示", "请先选择一个进程", parent=win)
                return False
            result["value"] = {"name": nm, "pid": pid}
            return True

        tree.bind("<Double-1>", lambda _: do_sel() and win.destroy())

        bf = tk.Frame(win, bg=LIGHT_SURFACE)
        bf.pack(fill=tk.X, padx=14, pady=(0, 12))
        ttk.Button(bf, text="取消", command=win.destroy).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(bf, text="选择",
                   command=lambda: do_sel() and win.destroy()).pack(side=tk.RIGHT)

        se.focus_set()
        win.wait_window()
        return result["value"]

    # ═══════════════════════════════════════════════════════════
    #  启停逻辑
    # ═══════════════════════════════════════════════════════════
    def _start(self):
        if self.running:
            return
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("提示", "请填写进程名")
            return
        vmin = self._parse_int(self.min_var.get(), 50)
        vmax = self._parse_int(self.max_var.get(), 950)
        if vmin > vmax:
            messagebox.showwarning("提示", "间隔下限 > 间隔上限")
            return
        self._save_config()
        self.stop_event.clear()
        t = threading.Thread(target=key_press_loop,
                             args=(self.stop_event, self.config_lock,
                                   self.shared_config),
                             daemon=True)
        t.start()
        self.worker_thread = t
        self.running = True
        log(f"启动 — 目标进程: {name}, 按键: {self.key_var.get().strip()}")
        self._resize_all()

    def _stop(self):
        if not self.running:
            return
        self.stop_event.set()
        self.running = False
        log("停止")
        self._resize_all()

    # ═══════════════════════════════════════════════════════════
    #  全局热键
    # ═══════════════════════════════════════════════════════════
    def _start_hotkey(self):
        hk = self.hotkey_var.get().strip()
        if hk:
            self.hotkey_mgr.register(
                hk, lambda: self.root.after(
                    0, lambda: self._stop() if self.running else self._start()))
        self.hotkey_mgr.start()

    def _stop_hotkey(self):
        self.hotkey_mgr.stop()

    def _toggle_topmost(self, on: bool):
        self.root.attributes("-topmost", on)
        self._start_hotkey() if on else self._stop_hotkey()

    def _toggle_log(self, on: bool):
        set_enabled(on)

    # ═══════════════════════════════════════════════════════════
    #  关闭窗口
    # ═══════════════════════════════════════════════════════════
    def _on_close(self):
        self._save_config()
        self._stop_hotkey()
        self._stop()
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=0.5)
        self.root.destroy()
