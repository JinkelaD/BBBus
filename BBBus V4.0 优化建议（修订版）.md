================================================================================
  BBBus V4.0 优化建议（修订版）
  生成日期：2026-08-12
  代码库规模：7 个 Python 文件，约 1348 行（与初版一致）
  评审方式：全量代码逐行复核 + 四角度独立评审
            架构（高见远）/ 工程（寇豆码）/ 测试（严过关）/ 产品（许清楚）
================================================================================

目录
  零、修订说明（相对初版的主要变更）
  一、总体评价（修订）
  二、高优先级（正确性 / 健壮性 / 架构）
  三、中优先级（可维护性与健壮性）
  四、低优先级（代码质量与风格）
  五、新增：测试与质量保障（QA 视角）
  六、新增：产品与体验（PM 视角）
  七、建议重构路线（修订）
  八、附录：模块职责图（更新）

================================================================================
  零、修订说明（相对初版的主要变更）
================================================================================

初版《BBBus V4.0 优化建议.txt》整体方向正确，但经全量代码复核与四角度评审，
发现**若干条目的行号/描述/修法有误**，且**完全缺失「测试」与「产品/体验」两个维度**。
本修订版的主要变更：

1. 【纠正严重度】P1-2（缓存锁）、P1-3（回调“泄漏”）均从「高」下调：
   - P1-2：`_hwnd_cache` 仅 worker 线程访问，无并发；`_proc_cache` 有 GIL 保护，
     最坏读到略旧快照，不崩溃 → 降为**低**。
   - P1-3：无真实“泄漏”，`EnumWindows` 同步调用、局部对象调用期存活；原“模块级预建
     回调”修法因闭包引用局部变量**不可编译** → 降为**低**，仅上提 `WINFUNCTYPE` 类型。

2. 【纠正错误修法】P1-4 初版给的 `except (psutil.NoSuchProcess, psutil.AccessDenied,
   Exception)` 中 `Exception` 是父类，等于“捕获一切”，**等于没改**。须改为仅捕获具体异常。

3. 【纠正错误理由/前提】
   - P3-1：初版称“psutil 经 key_worker 间接可用”不成立，需顶部 `import psutil`。
   - P3-2：gui 的 frozen 分支取 `sys._MEIPASS`，config/logger 取 `sys.executable`
     目录，**不能共用一个 `get_base_path()`**，须拆两个函数。
   - P3-3：窗口 `resizable(False, False)`，“频繁 resize 全量重绘”前提不成立 → 降为可选。
   - P3-4：鼠标按键**不应**塞进 VK_MAP（概念错误），仅补小键盘/符号键。
   - P3-8：`SetProcessDpiAwareness` 并未被官方正式弃用，`-4` 是 per-monitor v2，
     与值 `1`（系统级）是**不同感知级别，不可等同替换**。
   - P3-9：`scale(0.92)` 后 `scale(1/0.92)` 单周期自校正，非累积漂移，前提弱化。

4. 【新增关键遗漏（原文档未发现）】
   - A1（架构级）：`shared_config` 用“重新绑定”而非“原地更新”，导致运行中配置热更新
     **实际失效**（worker 持有的仍是启动时的旧 dict 引用）。
   - N1（正确性 bug）：占位符文本恰为合法输入值（如 `"f1"`/`"notepad.exe"`）时，
     `_collect_config` 会静默清空该字段 → 数据丢失。
   - Q1 / Q2 / Q5（三处 P1 级健壮性隐患）：发键不查返回值导致“假发送”、非法键致
     worker 永久空转、日志写失败拖垮线程。
   - 第五、六章：全新补充「测试与质量保障」「产品与体验」两大维度。

================================================================================
  一、总体评价（修订）
================================================================================

BBBus 是一个功能完整的 Windows 自动化按键工具，代码结构清晰、模块划分合理，
线程安全有基本保护、Canvas 自绘 UI 体验良好、配置持久化稳定。

经四角度复核，初版建议的“方向”基本正确，但**部分条目的事实基础有误**（严重度高估、
修法不可编译/等于没改），且**缺两整个维度**（测试、产品体验）。本修订版在保留有效建议
的同时，纠正了错误、补充了遗漏，并把“运行中配置热更新失效”“占位符撞合法值静默清空”
这两个**真正的正确性缺陷**提到应有高度。

================================================================================
  二、高优先级（正确性 / 健壮性 / 架构）
================================================================================

【P1-1】key_worker.py — 主键/副键互斥逻辑缺陷　【核实通过·修法需补全】
  位置：key_worker.py 第 141–153 行（初版写 143–153，实际从 141 起）
  问题：副键满足间隔时走 if 只发副键、else 才发主键，副键“吃掉”主键周期，主键频率下降。
  初版修法问题：片段引用了未定义的 `sub_vk`，直接照搬会 NameError。
  修订代码（完整可编译，主键始终发送、副键额外发送）：
    now = time.time()
    # 主键始终发送，不受副键影响
    _send_key_to_window(hwnd, vk)
    log(f"已向目标进程 {name} 发送 {target_key}")
    # 副键达到间隔时“额外”发送，不挤占主键周期
    if sub_key and (now - last_sub_send) * 1000 >= sub_key_interval:
        try:
            sub_vk = _get_vk(sub_key)
        except ValueError:
            sub_vk = None
        if sub_vk is not None:
            _send_key_to_window(hwnd, sub_vk)
            log(f"已向目标进程 {name} 发送副键 {sub_key}")
            last_sub_send = now
  优先级：高（保留）。注意 `last_sub_send` 仅在副键真正发出时更新。

【P1-2】key_worker.py — 模块级缓存缺锁　【严重度下调：高 → 低】
  位置：key_worker.py 第 16–21 行
  问题：初版称“两缓存被多调用方无锁访问”。实测：
    - `_hwnd_cache` 仅 worker 线程访问（单线程），无并发风险；
    - `_proc_cache` 被进程对话框主线程（gui.py 765）与 worker（key_worker 57）共享，
      但 CPython GIL 保证 dict 赋值原子，最坏读到略旧 TTL 快照，不崩溃。
  修订建议：为 `_proc_cache` 加一把锁并返回浅拷贝即可（见 Q8），不必如初版大改。
  优先级：低（由高下调）。

【P1-3】key_worker.py — EnumWindows 回调“泄漏”　【严重度下调：高 → 低·原修法不可行】
  位置：类型定义在 key_worker.py 第 66 行，调用在第 83 行
  问题：初版称“C 回调对象不断创建引起引用泄漏”**不准确**。`EnumWindows` 是同步阻塞调用，
    ctypes 回调实例在调用期被实参引用保持存活，返回后即可回收，不存在泄漏。
  初版修法不可行：`WNDENUMPROC(enum_proc)` 放模块级无法编译——`enum_proc` 是内部闭包，
    引用了 `pid/match_pids/result` 等局部变量，模块级拿不到。
  正确做法：仅把“类型”上提到模块级，回调实例因闭包状态必须每次新建（这没问题）：
    # 模块级（与 _hwnd_cache 相邻）
    _WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
    # 函数内：删除第 66 行，第 83 行改为
    user32.EnumWindows(_WNDENUMPROC(enum_proc), 0)
  优先级：低（由高下调，定性为“可不做/仅风格一致性”）。

【P1-4】gui.py — 瞄准镜裸 except 吞异常　【核实通过·初版修法错误，须纠正】
  位置：gui.py 第 683 行（`except:` 裸捕获，位于 `_target_window` 的 `clk` 内）
  问题：裸 `except` 会吞掉 `KeyboardInterrupt`/`SystemExit`，调试无迹可寻。
  初版修法错误：`except (psutil.NoSuchProcess, psutil.AccessDenied, Exception)` 中
    `Exception` 已涵盖前两者，等于“捕获一切”，**等于没改**。
  修订代码（只捕具体异常；`sys` 已在 gui.py 顶部导入）：
    try:
        R["name"] = psutil.Process(pv).name() if pv else ""
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        R["name"] = ""
  优先级：高（保留）。长远建议统一改用标准 `logging`（见 P1-5/P1-6 合并方案）。

【P1-5 + P1-6】logger.py — 每次开文件 + 写入失败崩溃线程　【核实通过·建议合并修复】
  位置：P1-5 在 logger.py 第 33–35 行；P1-6 在第 34 行
  问题：两条均属实。50ms 间隔下每秒约 20 次开/关文件；磁盘满/权限不足时 `open()` 失败，
    异常经 `log()` 冒泡到 `key_press_loop` 工作线程，导致按键循环终止。
  合并修订方案（保持句柄 + 行缓冲 + flush + 容错，绝不向上抛）：
    _log_file = None   # 惰性创建、保持打开

    def set_enabled(enable: bool) -> None:
        global _log_enabled, _log_file
        _log_enabled = enable
        if not enable and _log_file is not None:
            try: _log_file.close()
            finally: _log_file = None

    def log(msg: str) -> None:
        if not _log_enabled:
            return
        now = datetime.now()
        ts = now.strftime("%Y-%m-%d %H:%M:%S") + f".{now.microsecond // 1000:03d}"
        line = f"{ts} | {msg}\n"
        try:
            with _log_lock:
                if _log_file is None or _log_file.closed:
                    _log_file = open(LOG_PATH, "a", encoding="utf-8", buffering=1)
                _log_file.write(line)
                _log_file.flush()
        except OSError:
            pass   # 降级：写入失败不影响主流程（按键线程不崩溃）
  备选：直接用标准库 `logging.FileHandler`（自带缓冲/flush/错误隔离），更省心。
  优先级：高（保留 P1-5/P1-6）。

【A1｜新增·中→高】gui.py / key_worker.py — 配置热更新实际失效　【原文档完全遗漏】
  位置：gui.py `_cfg_to_shared`(242–244)、`_save_config`(619–622)；
        key_worker.py `key_press_loop`(108–156，持锁 copy 在 115–116)，
        gui.py 842 行 `args=(..., self.shared_config)`
  问题：worker 在 `_start` 时**按引用**拿到启动那一刻的 `shared_config` dict 对象；
    而 GUI 侧 `_cfg_to_shared`/`_save_config` 都是 `self.shared_config = d` **整体重新绑定**
    成新 dict，从不原地修改旧对象。worker 持有旧引用，`shared_config.copy()` 每轮拷贝的
    永远是启动时的配置。即：运行中去改 UI、或用瞄准镜/进程框改了 name/pid，**worker 全看不到**。
    当前每轮持锁 copy 的本意是“热更新”，却因引用被替换而实际失效。
  修订方案（最小改动，原地更新而非重新绑定）：
    def _cfg_to_shared(self, cfg: AppConfig):
        with self.config_lock:
            self.shared_config.clear()
            self.shared_config.update(cfg.to_dict())

    def _save_config(self):
        d = self._collect_config()
        with self.config_lock:
            self.shared_config.clear()
            self.shared_config.update(d)
        # ... 其余不变；worker 的 shared_config.copy() 保持不变即可生效
  优先级：高（原文档遗漏，建议补入高优先级）。若选择“启动即冻结”语义，则每轮的锁+copy
    是多余误导，应一并删除——二者须二选一，当前推荐支持热更新。

【Q1｜新增·高】key_worker.py — `_send_key_to_window` 不检查 PostMessageW 返回值
  位置：key_worker.py 第 90–105 行（调用在 102、104；log 在 147/153）
  问题：目标窗口已关闭/最小化到托盘/跨会话时 `PostMessageW` 返回 0，但代码忽略返回值，
    且仍 `log("已发送…")` 报“成功”，误导排查（假发送）。
  修订方案：函数返回 `bool`，调用方据返回值决定日志与缓存清理（见 Q3）。
    def _send_key_to_window(hwnd, vk: int, hold_ms: int = 5) -> bool:
        user32 = ctypes.windll.user32
        WM_KEYDOWN, WM_KEYUP = 0x0100, 0x0101
        sc = user32.MapVirtualKeyW(vk, 0)
        def _lp(repeat=1, sc=0, ext=False, ctx=0, prev=0, trans=0):
            return (repeat | (sc << 16) | (1 << 24 if ext else 0)
                    | (ctx << 29) | (prev << 30) | (trans << 31))
        ok = user32.PostMessageW(hwnd, WM_KEYDOWN, vk, _lp(sc=sc))
        if not ok:
            return False
        time.sleep(hold_ms / 1000.0)
        ok = user32.PostMessageW(hwnd, WM_KEYUP, vk, _lp(sc=sc, prev=1, trans=1))
        return bool(ok)
  优先级：高。

【Q2｜新增·高】gui.py / key_worker.py — 启动未校验按键合法性 → worker 永久空转
  位置：gui.py `_start`(826–848) 仅校验 `vmin>vmax`；错误发生在 key_worker.py 135–139
  问题：用户填非法键名（如 `"abc"`），`_start` 不拦截直接起线程；`key_press_loop` 在
    `_get_vk(target_key)` 抛 `ValueError`，被捕获后 `stop_event.wait(0.5); continue`——
    每 0.5s 空转、永不报错、UI 显示“运行中”。副键非法则被 `except ValueError: pass` 静默吞掉。
  修订方案：在 `_start` 起线程前（约 838 行之前）校验：
    from vk_map import VK_MAP
    key = self.key_var.get().strip().lower()
    if key and key not in VK_MAP:
        messagebox.showwarning("提示", f"不支持的输出按键: {key}"); return
    sub = self.sub_key_var.get().strip().lower()
    if sub and sub not in VK_MAP:
        messagebox.showwarning("提示", f"不支持的副输出按键: {sub}"); return
  优先级：高。

================================================================================
  三、中优先级（可维护性与健壮性）
================================================================================

【P2-1】gui.py — BBBusApp 类过大　【核实通过·克制拆分】
  位置：gui.py 第 197–888 行（约 692 行）
  问题：同时承担 UI 构建/配置 IO/热键/进程对话框/瞄准镜/启停/窗口管理，违反 SRP。
  修订意见：单窗口小工具不必过度拆分。最高性价比拆分是抽离 `ProcessDialog`
    （708–821，约 110 行）与 `CrosshairOverlay`/`_target_window`（631–697，约 67 行）；
    `KeyLoopController`（线程生命周期）收益有限、徒增间接层，不建议。
  优先级：中（保留，范围克制）。

【P2-2】config.py — from_dict/to_dict 手动维护字段　【核实通过·修法可用】
  位置：to_dict 第 30–42 行，from_dict 第 44–57 行
  问题：新增字段需改 3 处。
  修订代码（利用 dataclass + asdict；from_dict 过滤未知字段防回退默认被覆盖）：
    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "AppConfig":
        known = {f.name for f in dataclasses.fields(AppConfig)}
        return AppConfig(**{k: v for k, v in d.items() if k in known})
  优先级：中（保留）。

【P2-3】config.py — 配置损坏静默回退　【核实通过·修法需放宽并备份】
  位置：load_config 第 60–68 行，except 在第 66 行
  问题：损坏时静默回落默认，用户无感知。
  修订代码（备份损坏文件 + 告警；放宽异常以覆盖新 from_dict 可能的 TypeError）：
    def load_config() -> AppConfig:
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return AppConfig.from_dict(data)
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                corrupt = CONFIG_PATH + ".corrupt.bak"
                try:
                    if os.path.exists(corrupt):
                        os.remove(corrupt)
                    os.rename(CONFIG_PATH, corrupt)
                    print(f"[BBBus] 配置文件已损坏，已备份为 {corrupt}，回退默认配置")
                except OSError:
                    print("[BBBus] 配置文件损坏且无法备份，回退默认配置")
        return AppConfig()
  优先级：中（保留）。

【P2-4】gui.py — UI/配置手动双向同步　【核实通过·低侵入方案】
  位置：`_collect_config` 第 594–617 行，`_load_to_ui` 第 572–586 行
  问题：字段增删需同时改两处，易遗漏。
  方案（不引入双向绑定框架，用集中字段规范消除漂移）：
    _STR_FIELDS = [("name","name_var"),("pid","pid_var"),("target_key","key_var"),
                   ("sub_key","sub_key_var"),("hotkey","hotkey_var")]
    _INT_FIELDS = [("interval_min","min_var",50),("interval_max","max_var",950),
                   ("sub_key_interval","sub_interval_var",5000)]
    # _load_to_ui 遍历 set；_collect_config 遍历 get，整型走 _parse_int
    # 开关 topmost/log_enabled 仍单独处理
  优先级：中（保留）。

【P2-5】hotkey_manager.py — 回调异常静默吞没　【核实通过·修法需 import logger】
  位置：第 91–95 行，`except Exception: pass` 在第 94 行
  问题：热键回调内 bug 完全不可见。
  修订代码（hotkey_manager 顶部加 `from logger import log` + `import traceback`）：
    try:
        if self._callback:
            self._callback()
    except Exception:
        import traceback
        log(f"热键回调异常: {traceback.format_exc()}")
  注意：logger 默认关闭时“仅 log”仍不可见；要保证可见可改用 `print` 到 stderr，或
    在 `_poll` 顶层包 `self._root.report_callback_exception`。**不要去掉 try/except**，
    否则一次回调异常会中断第 99 行的 after 轮询。
  优先级：中（保留）。

【P2-7】config.py — 缺少配置迁移机制　【核实通过·路线图项】
  问题：`AppConfig` 无 `version` 字段；`load_config` 损坏才回退，字段改名无法迁移。
  修订意见：AppConfig 增 `version: int = 1`；`load_config` 读取后按版本执行迁移表；
    与 P2-3 合并（损坏先备份再重置 + 告警）。非代码缺陷，列入重构路线即可。
  优先级：中（保留）。

【N1｜新增·中】gui.py — 占位符文本恰为合法值 → 静默数据丢失　【原文档未提及·正确性 bug】
  位置：`_mk_entry` 第 413–448 行；`_collect_config` 第 596–599 行（`_val` 用 `v == ph` 判定）
  问题：`_val` 以“当前值 == 占位符文本”识别占位符，当合法输入恰好等于占位符时被误判清空：
    - `key_var` 占位符是 `"f1"`（339 行），默认 `target_key="f1"`。全新安装载入默认 `"f1"`
      → 显示为占位符样式 → 首次保存 `_collect_config` 返回 `""`，**主键被清空**。
    - `name_var` 占位符 `"notepad.exe"`（324 行）：若目标进程就叫 notepad.exe，瞄准镜/进程框
      回填后 `name=="notepad.exe"==占位符` → 保存为 `""`。
  修订方案：改用独立状态位，不用“值等于占位符”判定（可借 P3-11 的 `PlaceholderEntry` 一并解决）：
    # _mk_entry 中
    self._ph_vars[id(var)] = {"ph": placeholder, "active": ph_showing[0]}
    # _collect_config 的 _val 改为
    def _val(var, default=""):
        meta = self._ph_vars.get(id(var))
        if meta and meta["active"]:
            return default
        v = var.get().strip()
        return default if not v else v
  优先级：中（建议与 P3-11 一并处理；严重度高于初版对占位符的低定位）。

【Q3｜新增·中】key_worker.py — 窗口中途失效造成“假发送”
  位置：查找 130 → 发送 146/152；缓存 TTL 见第 21 行
  问题：第 N 次迭代刚校验窗口可见拿到 hwnd，用户恰在 PostMessage 前关闭窗口。因 Q1 未查
    返回值，此次静默失败，直到第 N+1 次迭代才经 `IsWindow` 发现窗口已死。状态不一致误导排查。
  修订方案（配合 Q1，发送失败立即清缓存，下次强制重查）：
    if not _send_key_to_window(hwnd, vk):
        _hwnd_cache.pop(cache_key, None)   # cache_key 由 name/pid 推导
        log(f"向 {name} 发送失败（窗口可能已关闭），下次重查")
        stop_event.wait(0.5); continue
  优先级：中（与 Q1 配套，边界加固）。

【Q4｜新增·中】config.py / key_worker.py — 写死真实 PID → 进程退出后静默空转
  位置：config 60–68（可能含写死 pid，默认 0 自动）；key_worker 55–63、74–76
  问题：若固定了某 pid 且该进程已退出/重启后 pid 变，`_find_window_by_process` 以
    `pid!=0` 走 `c_pid.value == pid` 过滤，找不到 → 返回 None → 永久空转无提示。
  修订方案：(a) `_start` 起线程前用 `psutil.pid_exists(pid)` 校验；(b) 循环内对固定 pid
    做存活探测，死了就停并提示：
    if pid and not psutil.pid_exists(pid):
        log(f"PID {pid} 已不存在，自动停止"); break
  优先级：中。

【Q6｜新增·中】gui.py / key_worker.py — 间隔仅校验 min>max，未校验负/零/超大
  位置：gui.py 833–834（解析）、835–837（仅 min>max）；key_worker 155–156
  问题：填 `interval_min=-50` 或 `0`，`random.randint` 接受，`stop_event.wait(负数)`
    立即返回 → **tight busy loop 占满 CPU**；极大值则单次等待过长。
  修订方案：`_start` 内补充边界校验：
    if vmin < 0 or vmax < 0:
        messagebox.showwarning("提示", "间隔必须为非负整数"); return
    if vmax > 60000:
        messagebox.showwarning("提示", "间隔上限建议 ≤ 60000ms"); return
    if vmin > vmax:
        messagebox.showwarning("提示", "间隔下限 > 间隔上限"); return
  优先级：中。

【Q7｜新增·中】gui.py / hotkey_manager.py — 热键快速连按抖动 + 回调异常静默
  位置：gui.py 861–867（`root.after(0, ...)`）；hotkey_manager 70–99，94–95
  问题：快速连按热键 `after(0,...)` 排队多个回调，逐个执行 toggle → “按一下却停了又起”的抖动；
    `_poll` 内 `except Exception: pass` 把回调内任何 bug 完全吞掉（呼应 P2-5）。
  修订方案：(a) 热键加去抖（如 300ms 内忽略重复触发）；(b) `_poll` 异常改为 `log`
    （见 P2-5）。
  优先级：中。

【Q10｜新增·中】gui.py / key_worker.py — 瞄准镜裸 except + 目标最小化到托盘空转
  位置：gui.py 683；key_worker 41（`IsWindowVisible` 要求可见）
  问题：除 P1-4 的裸 except 外，目标窗口若最小化到托盘（进程在但无可见窗口），
    `IsWindowVisible` 返回 False → 清缓存 → `EnumWindows` 找不到可见窗口 → None → 永久空转无提示。
  修订方案：收窄 except（见 P1-4）；对最小化场景，要么允许向“有效但不可见”窗口发键
    （`IsWindow` 为真即可，去掉可见性硬约束），要么在循环检测连续多次找不到可见窗口时 log 警告。
  优先级：中。

【PM-2｜产品·高】启动前不校验目标窗口是否存在，状态灯误导
  位置：gui.py `_start` 826–848；`_resize_all` 558–560；key_worker 130–133
  问题：填了进程名但目标未开/未在前台，点“启动”看到绿点和“运行中”，以为生效，实际空转。
  修订方案：启动瞬间用 `_find_window_by_process(name, pid)` 探一次；找不到则弹窗
    “未找到窗口『name』，请确认目标已启动”并中止启动（或进入“等待窗口…”状态，而非“运行中”）；
    持续找不到应周期性在状态栏/日志提示，而非静默死循环。
  优先级：高（与 Q2/Q4 协同，属同一根因的不同表现）。

【PM-4｜产品·高】“置顶”开关与全局热键强耦合，关置顶静默停用热键
  位置：gui.py `_toggle_topmost` 872–874
  问题：关置顶 → `_stop_hotkey()`，开置顶 → `_start_hotkey()`；二者语义无关却一个开关联动，
    用户极易困惑且无提示。
  修订方案：将“置顶”与“热键”解耦为两个独立开关；若必须关联，切换时给出 tooltip/状态提示；
    热键启用态应在状态栏可见。
  优先级：高。

【PM-6｜产品·中】进程对话框：选父节点（同名多 PID）锁死首个 PID
  位置：gui.py `_show_process_dialog` 708–821（info[parent] 在 777；do_sel 在 804）
  问题：对 chrome/微信等多实例程序，点名称行返回 `pids[0]`（任意实例 PID）写进 config；
    该进程一退出，PID 失效 → 静默空转（见 Q4）。
  修订方案：选中父节点（进程名）时返回 `pid=0`（按名称自动匹配）；或强制展开要求选具体子 PID；
    或在父节点行注明“选此项=按名称匹配全部实例”。
  优先级：中。

【PM-7｜产品·中】“副输出键/副键间隔”语义与单位不清
  位置：config.py `sub_key_interval=5000`；gui.py 355–362 占位符仅 “ms”
  问题：用户不知“副键”是“额外再发”还是“替代主键”；不知单位毫秒；填 “5” 以为 5 秒实为 5ms。
  修订方案：间隔框后加“毫秒”单位标签；副输出键标签加 helper“可选：每隔 N 毫秒额外发送此键”；
    默认值/范围在 tooltip 提示（P1-1 修复后文案须明确“主键照常发，副键每隔 N 毫秒额外发一次”）。
  优先级：中。

【PM-8｜产品·中】配置写入真实 PID，换机/重启即失效且静默空转
  位置：瞄准镜/进程框回填 pid_var → config.json；key_worker 44–46
  问题：目标程序重启（PID 变）或换机器后旧 PID 失效，工具“运行中”却毫无输出。
  修订方案：默认推荐“仅按进程名匹配（pid=0）”，PID 仅作可选“锁定”；设置的具体 PID 找不到时
    自动回退按名称匹配并提示；UI 上提示“锁定 PID 进程重启后可能失效”（呼应 Q4）。
  优先级：中。

【PM-9｜产品·中】全局热键默认 ctrl+shift+k 易冲突、无提示、无反馈
  位置：config.py 26；hotkey_manager 轮询；gui.py `_start_hotkey` 861–867
  问题：Ctrl+Shift+K 与不少软件冲突；注册失败/置顶关闭时按键无反应且不知原因；触发无感知。
  修订方案：默认热键改更低冲突率组合或允许自定义并实时校验；注册失败/置顶关闭时明确提示；
    触发启停给 toast/音效反馈；状态栏常显“热键：Ctrl+Shift+K 已启用/未启用”（呼应 Q7）。
  优先级：中。

【PM-10｜产品·中】运行中修改配置不生效、无提示
  位置：gui.py shared_config 仅 `_start`/`_on_close` 经 `_save_config` 更新（与 A1 同源）
  问题：运行中改间隔/按键，不影响正在跑的循环（除非 A1 已修复热更新）。
  修订方案：A1 修复后支持热更新；否则运行中将这些输入禁用（灰显）或加注“修改将在下次启动生效”。
  优先级：中。

【PM-13｜产品·中】热键字段非法时静默不注册
  位置：hotkey_manager `register` 48–61；gui.py `_start_hotkey` 忽略返回值
  问题：用户填了不被支持的按键组合，保存/启动毫无报错，热键实际无效。
  修订方案：保存/启动时校验热键合法性，非法则 messagebox 提示并标红输入框。
  优先级：中。

【PM-14｜产品·低/中】间隔数值缺边界校验（与 Q6 同源，从体验视角补强）
  位置：gui.py `_parse_int` 588–592；key_worker `random.randint` 155
  问题：误填 0/负数/极大值，行为异常无提示。
  修订方案：同 Q6，启动时校验区间合理（1~60000ms），越界提示。
  优先级：低（与 Q6 合并处理）。

================================================================================
  四、低优先级（代码质量与风格）
================================================================================

【P3-1】gui.py — psutil 重复 import　【核实通过·初版理由错误】
  位置：第 496 行（`_on_pid_focusout` 内）、第 632 行（`_target_window` 内）
  纠正：初版称“psutil 经 key_worker 间接可用”**不成立**（`from key_worker import ...`
    不会把 psutil 引入 gui 命名空间；gui 顶部确实无 `import psutil`）。
  修订：顶部加 `import psutil`，删除两处方法内 import。
  优先级：低（保留）。

【P3-2】路径解析重复　【核实通过·不能一刀切】
  位置：config.py 11–14、logger.py 11–14、gui.py 231–234
  纠正：config/logger 的 frozen 分支取 `sys.executable` 目录；gui `_set_app_icon` 的
    frozen 分支取 `sys._MEIPASS`（PyInstaller 数据目录，用于打包的 .ico）。二者语义不同，
    **不能共用一个 `get_base_path()`**。
  修订（utils.py 提供两个函数）：
    def get_app_dir() -> str:        # 用于 config.json / BBBus.log
        if getattr(sys, "frozen", False):
            return os.path.dirname(sys.executable)
        return os.path.dirname(os.path.abspath(__file__))

    def get_resource_dir() -> str:   # 用于打包内的图标等资源
        if getattr(sys, "frozen", False):
            return sys._MEIPASS
        return os.path.dirname(os.path.abspath(__file__))
  优先级：低（保留）。

【P3-3】_resize_all 全量重绘　【前提弱化·降为可选】
  位置：`_resize_all` 第 513 行，绑定 `<Configure>` 在第 280 行；`resizable(False, False)` 在 202 行
  纠正：窗口不可缩放，用户无法拖拽，`<Configure>` 基本只在启动/启停/DPI 变化时触发，
    不频繁。真正被频繁调用的场景是启停（`_start` 848、`_stop` 856 各一次）。
  修订：保持现状即可；若未来放开 `resizable` 再加 100ms 防抖。当前降为“可选优化”。
  优先级：低（维持，价值有限）。

【P3-4】vk_map.py — 按键映射不完整　【部分正确·“鼠标”建议错误】
  位置：VK_MAP 第 21–36 行
  纠正：① 当前够用——config.json 用 `target_key="1"`、`sub_key="2"`，均在 VK_MAP 内；
    ② 小键盘/符号键（numpad 0x60–0x6F、`, . / ; ' [ ] \ - =` 等 VK）属合理增强；
    ③ **鼠标按键不应放进 VK_MAP**（鼠标点击不是键盘虚拟键码，概念错误）；若需鼠标支持，
      应另起 `SendInput` 鼠标事件通道。
  优先级：低（保留，剔除“鼠标”项，明确范围）。

【P3-5】vk_map.py — _MOD_FLAGS 命名　【核实通过·需同步改 hotkey_manager】
  位置：vk_map.py 第 39 行；被 hotkey_manager.py 第 12、79 行使用
  修订（改名并同步两处）：vk_map.py 第 39 行 `MOD_FLAGS = [...]`；
    hotkey_manager.py 第 12 行改为 `from vk_map import VK_MAP, MOD_MAP, MOD_FLAGS`；
    第 79 行改为 `for flag, vk_mod in MOD_FLAGS:`。
  优先级：低（保留）。

【P3-6】gui.py — _parse_int 默认值语义　【当前安全·建议去掉默认值】
  位置：第 588 行（`def _parse_int(self, s, default=50)`）
  问题：所有调用点（610/611/833/834）都显式传 default，当前无 bug；但 `default=50` 形同摆设，
    未来某处漏传会静默用错值。
  修订：去掉默认值，强制显式传入：
    def _parse_int(self, s: str, default: int) -> int:
        try: return int(s.strip())
        except ValueError: return default
  优先级：低（保留）。

【P3-7】main.py — 裸 except 吞异常　【核实通过·修法可用】
  位置：第 18 行 `except Exception: pass`
  修订：至少打印告警。
    except Exception as e:
        print(f"[BBBus] DPI/AppUserModelID 初始化失败: {e}")
  优先级：低（保留）。

【P3-8】main.py — 使用“已弃用”DPI API　【“已弃用”说法不准确·-4 非等同替换】
  位置：第 17 行 `ctypes.windll.shcore.SetProcessDpiAwareness(1)`
  纠正：① `SetProcessDpiAwareness`（shcore）**未被官方正式弃用**，只是被
    `SetProcessDpiAwarenessContext`（user32，Win10 1703+）取代，当前仍可用；
    ② 值 `1` 是 `PROCESS_SYSTEM_DPI_AWARE`（系统级），`-4` 是
    `DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2`（每显示器 v2），二者是**不同感知级别，
    不能简单互换**。
  修订（优先 per-monitor v2，失败回退系统级；合并 P3-7 的告警）：
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Jinkela.BBBus")
            try:
                ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)   # 每显示器 v2
            except Exception:
                ctypes.windll.shcore.SetProcessDpiAwareness(1)          # 回退系统级（仍有效）
        except Exception as e:
            print(f"[BBBus] DPI/AppUserModelID 初始化失败: {e}")
  优先级：低（保留，说明已修正）。

【P3-9】gui.py — Canvas scale 精度丢失　【前提弱化·实际自校正】
  位置：第 484–489 行（`_press` scale 0.92，`_release` scale 1/0.92）
  纠正：每次按下×0.92、释放×1/0.92，单周期净缩放≈1.0，**自校正而非累积漂移**；
    26px 图标下浮点误差约 1e-15，肉眼/像素级不可见。初版“多次点击后图标逐渐偏移”不成立。
  建议（可选，更稳妥）：用“按下状态”切换而非连续累乘：
    pressed = False
    def _press(e):
        nonlocal pressed
        if not pressed:
            cv.scale("all", SIZE//2, SIZE//2, 0.92, 0.92); pressed = True
    def _release(e):
        nonlocal pressed
        if pressed:
            cv.scale("all", SIZE//2, SIZE//2, 1/0.92, 1/0.92); pressed = False
  优先级：低（维持，价值有限）。

【P3-10】全局缺类型注解　【核实通过·给公共接口加】
  位置：全局（如 `_find_window_by_process` 无返回注解、`shared_config` 无内部结构）
  修订：至少给公共接口加注解并引入 mypy。示例：
    def _find_window_by_process(name: str, pid: int = 0) -> "int | None": ...
    def get_running_processes(refresh: bool = False) -> dict[str, list[int]]: ...
    self.shared_config: dict[str, "str | int | bool"] = {}
  优先级：低（保留）。

【P3-11】gui.py — 占位符系统复杂　【核实通过·封装为类顺带修复 N1】
  位置：`_mk_entry` 第 413–448 行
  问题：闭包 `ph_showing` + `trace_add` + 多事件绑定，逻辑分散。
  方案：封装 `PlaceholderEntry(tk.Frame)`，内部持有 `self._placeholder` 与 `self._showing`，
    对外暴露 `get()`（占位时返回 `""`）与 `is_placeholder()`。**同时消除 N1 的“字符串相等判定”隐患**。
  优先级：低（保留，建议与 N1 一并处理）。

【N2｜新增·低】gui.py — `str(var)` 作字典 key 的脆弱性
  位置：`_mk_entry` 第 415 行 `self._ph_vars[str(var)]`；`_collect_config` 第 598 行
  问题：`str(tk.StringVar())` 返回 Tcl 内部变量名（如 `"PY_VAR0"`），属实现细节依赖；
    变量重建或名称复用即失效。应改用 `id(var)`，或如 N1 将状态直接挂到 var 对象上。
  优先级：低（与 N1 一并处理）。

【N3｜新增·低】gui.py — pid 解析容错实际已足够（仅记录，无动作）
  位置：`_collect_config` 第 601–605 行
  核对结论：`pid_str` 已 strip，`int()` 失败被 `except ValueError` 兜回 0；占位符 `"自动检测"`
    经 `_val` 返回 `""` → pid=0。逻辑已健壮，无需改动。唯一连带风险是 N2 的 `str(var)` key。
  优先级：低（仅记录）。

【A2｜新增·低】gui.py — worker 为 daemon 线程，异常退出无清理
  位置：gui.py 843 行 `daemon=True`；`_on_close` 882–888 的 `join(timeout=0.5)`
  问题：正常 Stop 时 0.5s 通常够；但若 worker 正卡在 `_find_window_by_process` 时触发关闭，
    join 可能超时，随后因 `daemon=True` 被强制终结（无干净收尾）。
  修订：超时提到 1–2s，或 worker 退出路径加 `finally` 做日志收尾（与 P2-6 同源，合并处理）。
  优先级：低。

【A3｜新增·低】hotkey_manager 与 BBBusApp 双向耦合 / 重复注册
  位置：gui.py `_start_hotkey` 861–867、`_toggle_topmost` 872–874；hotkey_manager `_poll` 70–99
  问题：`TkHotkeyManager` 回调经 `root.after(0, ...)` 反向调用 BBBusApp 启停。Tk 单线程事件循环下
    `after(0)` 与主线程其他调用串行，故“重入”实际安全（无真正并发重入）。但两点值得改：
    (1) `_start_hotkey` 每次 `register()` 新 lambda 再 `start()`（`start` 因 `_active` 已真而
    no-op），靠 register 覆盖旧回调勉强可用，应显式幂等/解注册；(2) 把“切换”语义下沉为
    `hotkey_mgr` 的 toggle 回调以解耦。
  优先级：低。

【A4｜新增·低】gui.py — `self.running` 无锁（仅记录，无需改动）
  位置：gui.py 多处（`_start`/`_stop`/`_resize_all`/`_on_close` 改写 `self.running`）
  问题：所有改写都在主线程（热键回调经 `after(0)` 也落主线程），worker 从不读 `self.running`
    （只信 `stop_event`），无跨线程竞争，当前安全。
  优先级：低（仅记录）。

【Q8｜新增·低】key_worker.py — 缓存并发竞态真实严重度评估（修正初版 P1-2 过高判断）
  位置：key_worker.py 16–21、159–173；gui.py 765
  评估：`_hwnd_cache` 仅 worker 读写，无竞态；`_proc_cache` 是主线程与 worker 共享，但字典
    赋值原子，当前不崩溃，仅存在“holder 看到刷新后新字典”的轻微一致性问题。
  修订（最小加固）：加锁 + 返回浅拷贝防误改：
    _cache_lock = threading.Lock()
    # get_running_processes 中
    with _cache_lock:
        if not refresh and now - _proc_cache["time"] < _PROC_CACHE_TTL:
            return dict(_proc_cache["data"])
        ...
        _proc_cache["data"] = result
        return dict(result)
  优先级：低（与 P1-2 合并处理）。

【Q9｜新增·低/中】hotkey_manager.py — `user32 = ctypes.windll.user32` 顶层导入阻断非 Win 单测
  位置：hotkey_manager.py 第 14 行
  问题：该语句在**模块导入期**执行，非 Windows（Linux CI）上 `ctypes.windll` 不存在 →
    `ImportError` → 整个模块（含纯逻辑 `parse_hotkey`）无法 import，单测全挂。这是项目
    “零测试”且“无法上 CI”的根因之一（详见第五章）。
  修订（延迟加载或平台守卫）：
    import sys
    user32 = ctypes.windll.user32 if sys.platform == "win32" else None
    def _poll(self):
        u = user32 or ctypes.windll.user32
  改完后 `parse_hotkey` 可在 Linux 上直接单测。
  优先级：低（测试前置条件，与第五章协同）。

【Q11｜新增·低】gui.py — 配置解析逻辑与 UI 强耦合，无法纯单测
  位置：gui.py 588–592（`_parse_int`）、594–617（`_collect_config`）
  问题：二者是 `BBBusApp` 实例方法，实例化需完整 Tk 环境，纯逻辑无法在 Linux 上单测
    （初版 P3-6 已提默认值语义问题）。
  修订（抽成模块级纯函数）：
    def parse_int(s: str, default: int) -> int:
        try: return int(s.strip())
        except ValueError: return default
    def build_config_dict(vars, toggles) -> dict: ...   # 集中字段映射，防漏字段
  优先级：低（与 P3-6/Q11 协同，测试前置条件）。

【Q12｜新增·低】key_worker.py — PID 复用竞态导致“按键发错窗口”（已知边界）
  位置：key_worker.py 43–50、73–80
  问题：按 pid 找到窗口后、到真正 PostMessage 之间，该 pid 可能被系统回收并分配给另一进程，
    按键发到错误窗口。长时间运行（数小时）才偶发，难以彻底消除。
  修订：在发送前用 `psutil` 复核 `pid→name` 仍匹配目标名（不匹配则重查）；或在文档标注此边界，
    不作为本次必改项。
  优先级：低（文档化即可）。

【Q13｜新增·低】key_worker.py — `get_running_processes` 返回共享可变字典引用
  位置：key_worker.py 第 162 行
  问题：返回 `_proc_cache["data"]` 同一对象，若调用方误改会污染全局缓存。
  修订：同 Q8，返回 `dict(_proc_cache["data"])` 浅拷贝。
  优先级：低（与 Q8 合并）。

================================================================================
  五、新增：测试与质量保障（QA 视角）
================================================================================

> 初版文档第二~五章几乎无测试内容。以下补齐可落地的测试体系。原始文档零自动化测试，
> 且因 Q9 的顶层 `windll` 导入，纯逻辑也无法在 Linux/CI 上跑。

1. 测试策略总览
   - 分层：① 纯逻辑单测（任意 OS，pytest）：映射表/配置序列化/日志/热键解析/键名解析/间隔校验；
            ② tkinter 无头/虚拟事件（Linux `xvfb-run` 或注入 fake root）：UI 配置收集、启停校验、热键轮询；
            ③ 真实 Windows 手动验收：真实按键送达、瞄准镜、系统级热键、托盘窗口、磁盘日志。
   - 工具：pytest + pytest-cov + pytest-mock；Linux GUI 单测可选 pytest-xvfb。
   - 工程：新增 `tests/` 与 `pyproject.toml`（`[tool.pytest.ini_options]` 设 testpaths/testpaths；
    `tests/conftest.py` 用 `tmp_path` + `monkeypatch` 隔离 `CONFIG_PATH`/`LOG_PATH`）。

2. 模块可测性评估表
   | 模块 | 依赖 Windows? | 推荐测试方式 | 前置 |
   |---|---|---|---|
   | vk_map.py | 否（纯数据） | 纯单测 | 可直接测 |
   | config.py | 否 | 纯单测（tmp_path） | 可直接测 |
   | logger.py | 否 | 纯单测（monkeypatch LOG_PATH） | 可直接测 |
   | key_worker._get_vk / get_running_processes | 导入期否，psutil 跨平台 | 纯单测 | 可直接测；窗口函数需 Win |
   | hotkey_manager.parse_hotkey | 逻辑否，但顶层 windll 阻断 | 先修 Q9 | 需改 Q9 |
   | gui._parse_int / _collect_config | 需先抽离 | Q11 后纯单测 | 需改 Q11 |
   | gui.BBBusApp 整体 | 实例化需 Tk；瞄准镜/热键需 Win | xvfb+虚拟事件；热键/瞄准镜留 Win | 部分可测 |
   | key_worker 窗口函数 | 是 | Win 上 mock.patch 替换 ctypes.windll.user32 做“假窗口”断言 | Win/mock |

3. 关键测试用例清单（至少覆盖）
   - vk_map：VK_MAP 所有值为合法 VK（0x01~0xFF、正整数、无重复撞键）、键名全小写；
     MOD_MAP 含 4 修饰键且 `<alt>`/`alt` 一致；MOD_FLAGS 与 MOD_MAP 标志位一一对应。
   - config：to_dict 含全部 11 字段；from_dict↔to_dict 往返一致；from_dict 缺字段→默认；
     多余字段→忽略不崩；load_config 文件缺失→默认；load_config 损坏 JSON→默认（建议 logging.warning，
     呼应 P2-3）；合法文件→正确解析；save+load 文件级往返。
   - key_worker：_get_vk 正常映射 / 非法键抛 ValueError；get_running_processes 缓存 TTL；
     修复后 _send_key_to_window 返回 bool 且 PostMessage 失败时返回 False；修复后
     _find_window_by_process 窗口关闭后返回 None 并清缓存。
   - hotkey_manager：parse_hotkey("ctrl+shift+k")→(mod, vk) 正确；大小写/空格容忍；
     缺按键→ValueError；未知片段→ValueError；仅修饰键→ValueError；"f1"单独→(0, VK)；
     修复后 _poll 在 key-down 边沿触发一次回调（mock GetAsyncKeyState 验证边沿去重）。
   - gui（需 Q11 抽离后）：_parse_int(" 50 ")→50；_parse_int("abc",50)→50；
     间隔校验 vmin>vmax 提示、vmin<0 处理；副键非法时被跳过；Q2 修复后非法 target_key 在 _start 被拦下。
   - logger：set_enabled 开关；禁用时不写文件；启用时写入格式 `YYYY-MM-DD HH:MM:SS.mmm | 消息`；
     修复后（Q5）向不可写路径 log() 不抛异常。

4. 测试代码骨架（仅示意）
   ```python
   # tests/test_config.py
   from config import AppConfig, load_config, save_config
   import json, tempfile, os

   def test_from_to_dict_roundtrip():
       c = AppConfig(name="notepad.exe", target_key="f1", pid=1234)
       assert AppConfig.from_dict(c.to_dict()).to_dict() == c.to_dict()

   def test_load_corrupt_json_returns_default(tmp_path, monkeypatch):
       p = tmp_path / "config.json"
       p.write_text("{not valid json", encoding="utf-8")
       monkeypatch.setattr("config.CONFIG_PATH", str(p))
       assert load_config() == AppConfig()   # 静默回退 + 应补充 logging.warning

   # tests/test_hotkey.py  (需先修 Q9)
   from hotkey_manager import parse_hotkey
   import pytest
   def test_parse_normal():
       mod, vk = parse_hotkey("Ctrl+Shift+K")
       assert vk == 0x4B
   def test_parse_missing_key():
       with pytest.raises(ValueError):
           parse_hotkey("ctrl")          # 只有修饰键
   def test_parse_unknown():
       with pytest.raises(ValueError):
           parse_hotkey("ctrl+zzz")
   ```

5. CI 限制与本地验收清单
   - CI 限制：项目依赖 Windows `ctypes.windll`（Q9 修复后仅剩窗口相关函数）；真实 GUI、真实目标窗口、
     系统级热键均无法在 Linux runner 运行。
     - 可行：Linux CI 跑“纯逻辑单测 + 注入 fake root 的 parse_hotkey/_poll 逻辑”；
       Windows 自托管 runner 跑 mock 版窗口函数与手动验收。
     - 建议：pyproject.toml 加 pytest 与 pytest-cov，CI 失败阈值先设 0 报错阻断（当前覆盖率为 0）。
   - 本地验收清单（真实 Windows，人工勾选）：
     1. 启动/停止按钮切换状态灯与文案正确；
     2. 输出按键填 "abc" → 弹窗提示且不空转（验证 Q2）；
     3. 间隔下限>上限 → 提示；填负数 → 提示（验证 Q6）；
     4. 热键 Ctrl+Shift+K 真实切换启停，快速连按不抖动（验证 Q7）；
     5. 置顶开关同步热键注册/注销（验证 PM-4）；
     6. 开启日志后 BBBus.log 生成、格式含毫秒、高频下不卡顿、磁盘满不崩（验证 Q5）；
     7. 运行中关闭目标窗口 → 下次迭代自动重查，日志体现“发送失败/重查”（验证 Q1/Q3）；
     8. 目标最小化到托盘 → 行为符合预期（验证 Q10）；
     9. 进程浏览对话框列出进程、搜索过滤、选择回填 PID/名称（验证 PM-6）；
     10. 配置持久化：重启后还原；config.json 改坏 → 回退默认且提示（验证 P2-3）；
     11. 副输出键逻辑：合法副键按间隔发送、非法副键被跳过（验证 P1-1 改后+Q2 副键分支）；
     12. 固定 PID 指向已退出进程 → 启动即提示、不空转（验证 Q4）。

================================================================================
  六、新增：产品与体验（PM 视角）
================================================================================

> 初版建议全为工程/架构视角，本文补全用户视角。每条标注【性质】与【优先级】。

【PM-1｜产品·高】占位符与真实输入易混淆，存在“静默空转”陷阱
  当前行为：`_mk_entry` 把占位符直接写入 StringVar 以灰色显示；`_collect_config` 用
    “值==占位符则视为空”过滤。
  痛点：① 占位符 "f1"（输出按键）本身即是合法按键名——用户清空再点开别处，框重新显示灰色 "f1"，
    启动时 `_collect_config` 把它当占位符丢弃 → `target_key=""` → worker `_get_vk("")` 抛错后
    continue（key_worker 137–139），**界面“运行中”却一个键都不发**。② "ms" 占位符不像数值提示。
  建议：占位符用“不可能是合法值”的提示文案（"如 f1""毫秒 50~950"）；或在输入框旁加独立单位标签；
    启动前强制校验 target_key 非空且合法（见 PM-2/Q2）。
  优先级：高（根因即 N1，二者合并修复）。

【PM-3｜产品·中】运行中状态仅靠颜色区分，停止按钮灰显易被忽略
  当前行为：`_resize_all` 537–551 用绿/红药丸区分，未运行时“停止”白底灰字（点击仅静默 return）；
    状态仅 6px 圆点 + 文字。
  痛点：① 红/绿对色弱用户不可辨；② 灰显“停止”像禁用按钮；③ 启动后若窗口遮住 BBBus 看不到“发键”迹象。
  建议：运行状态加文字/图标（“● 运行中”/“○ 已停止”）；“停止”即便未运行也应有常态可点样式；
    运行态给窗口标题栏或边框加高亮色带。
  优先级：中（纯 UI/文案）。

【PM-5｜产品·中】瞄准镜无操作指引、失败无反馈，多屏/DPI 下定位不准
  当前行为：`_target_window` 点 ⊙ 后主窗隐藏、准星跟随光标；左键取窗口、右键/Esc 取消，无任何文字说明；
    取不到窗口名时 `R["name"]` 为空 → 字段不更新也不报错。
  痛点：① 首次使用不知“左键选窗口、右键/Esc 取消”；② 选到无权限/特殊窗口静默无反应；
    ③ 多屏 DPI 不一致时 `GetCursorPos` 物理像素与 Tk 逻辑像素偏差，准星可能不居中。
  建议：准星旁显示“点击目标窗口 · 右键/Esc 取消”；取失败弹 toast；跨屏 DPI 用物理像素坐标并对准星做适配。
  优先级：中（UI + 少量逻辑）。

【PM-11｜产品·中】字段无 tooltip/引导，图标按钮 ⊙☰ 含义不明
  当前行为：表单无说明；"☰"(浏览进程)、"⊙"(瞄准选窗) 图标按钮（gui 297–300、457–490）无 tooltip。
  痛点：首次打开看到一堆占位符，不知先点哪个、怎么选目标，上手成本高。
  建议：每个输入加 tooltip；给 ⊙、☰ 加 hover 提示；考虑首屏一行使用提示或“?”帮助入口。
  优先级：中（纯 UI/文案）。

【PM-12｜产品·低】日志开关开启后无应用内查看入口
  当前行为：顶部“日志”开关开启后只写文件，UI 内看不到日志，也无“查看日志”入口。
  痛点：开启日志却无法确认是否真在发键（结合空转风险，用户尤其需要“看得到发了没”）。
  建议：运行时在状态栏滚动显示最近一条日志，或提供“打开日志”按钮。
  优先级：低（纯 UI/文案）。

【增强建议（非必须）】
  1. 系统托盘最小化 + 隐藏窗口仍可热键启停（与 PM-4 解耦配合）。
  2. 按键次数统计 / 实时状态：状态栏显示“已发送 N 次”“本次运行 X 秒”，直接消解“到底发没发”焦虑。
  3. 启停音效 / Toast 反馈：开始、停止、热键触发、目标窗口未找到时给轻量提示。
  4. 配置方案管理（多目标/导入导出）：支持保存多套“目标配置”方案并一键切换，导出/导入 config.json，
     解决 PM-8 的便携性与多场景复用问题。

================================================================================
  七、建议重构路线（修订）
================================================================================

  第一阶段（本次迭代，预计 2-3 小时）— 正确性优先
    1. 修复 P1-1 主键/副键互斥（含 sub_vk 补全）
    2. 修复 P1-4 瞄准镜裸 except（改只捕具体异常）
    3. 合并修复 P1-5/P1-6 logger（保持句柄 + 容错）
    4. 修复 A1 shared_config 热更新失效（原地更新）
    5. 修复 Q1 发键返回值检查 + Q2 启动校验按键合法性 + Q5 日志容错（三者同源，一并做）
    6. 修复 N1 占位符撞合法值静默清空（与 P3-11 一并）

  第二阶段（V4.1，预计 4-6 小时）— 健壮与可维护性
    7. P1-2/Q8 缓存加锁（低风险卫生）
    8. P2-2 用 dataclasses.asdict 简化 to_dict/from_dict
    9. P2-3 配置损坏备份 + 告警；P2-7 加 version 字段与迁移
    10. P2-4 集中字段规范消除 UI/配置同步漂移
    11. P2-5 热键回调异常记录（log）
    12. Q3/Q4/Q6/Q7/Q10 边界健壮化（窗口失效、PID 锁死、间隔边界、热键去抖、最小化空转）
    13. PM 类产品项：PM-2 启动校验窗口、PM-4 置顶/热键解耦、PM-6 父节点返回 pid=0、
        PM-7/PM-9/PM-13 文案与热键校验、PM-10 运行中配置处理

  第三阶段（V4.2，预计 3-4 小时）— 质量保障与体验
    14. 引入 pytest（先修 Q9/Q11 让纯逻辑可测），覆盖 vk_map/config/logger/hotkey
    15. P3-2 抽 get_app_dir/get_resource_dir；P3-5 改名 MOD_FLAGS；P3-6 去默认值；
        P3-7/P3-8 DPI 修法；P3-10 类型注解 + mypy
    16. P3-11 占位符封装为 PlaceholderEntry（顺带修 N1/N2）
    17. P2-1 抽离 ProcessDialog / CrosshairOverlay
    18. 产品增强：PM-3 状态文字化、PM-5 瞄准镜指引、PM-11 tooltip、PM-12 日志入口、
        托盘/统计/Toast/方案管理（见第六章增强建议）

================================================================================
  八、附录：模块职责图（更新）
================================================================================

  main.py ─── 入口，DPI/AppUserModelID 初始化（P3-7/P3-8 修正）
    │
    ├── gui.py ─── 主窗口 UI (BBBusApp, 197–888 行)
    │   ├── 输入框 + 占位符系统（N1/P3-11 缺陷，建议 PlaceholderEntry）
    │   ├── Canvas 按钮/开关/卡片
    │   ├── 瞄准镜 (CrosshairOverlay → P2-1 建议抽离；P1-4 裸 except)
    │   ├── 进程对话框 (ProcessDialog → P2-1 建议抽离；PM-6 父节点锁死 PID)
    │   ├── 启停逻辑（A1 热更新失效；Q2 启动校验；PM-2 窗口校验）
    │   └── 全局热键（PM-4 与置顶耦合；Q7 去抖；P2-5 异常记录）
    │
    ├── config.py ─── 配置持久化 (AppConfig + JSON)
    │   └── P2-2 asdict / P2-3 损坏备份 / P2-7 version 迁移
    │
    ├── hotkey_manager.py ─── 全局热键轮询 (TkHotkeyManager)
    │   └── Q9 顶层 windll 阻断单测 / P2-5 异常记录 / P3-5 MOD_FLAGS
    │
    ├── key_worker.py ─── 按键工作线程 + 窗口查找
    │   ├── P1-1 主键/副键互斥（已修）
    │   ├── Q1 发键返回值 / Q3 窗口中途失效
    │   ├── P1-2/Q8 缓存锁 / P1-3 回调类型上提（低风险）
    │   └── 依赖 vk_map.py 的按键映射
    │
    ├── vk_map.py ─── 按键名 ↔ 虚拟键码映射（P3-4 补小键盘/符号；P3-5 改名）
    │
    └── logger.py ─── 线程安全日志写入（P1-5/P1-6/Q5 保持句柄+容错）

  【新增维度】测试：tests/（pytest，需先修 Q9/Q11）— 详见第五章
  【新增维度】产品：占位符/瞄准镜/进程框/热键/状态栏体验 — 详见第六章
================================================================================
