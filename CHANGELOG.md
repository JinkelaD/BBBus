# CHANGELOG

BBBus 的所有重要变更记录于此。

格式参考 [Keep a Changelog](https://keepachangelog.com/)，版本号遵循 [Semantic Versioning](https://semver.org/)。

## [4.0.1] - 2026-10-14

### 优化 (Optimized)
- **key_worker**：修复主键/副键互斥逻辑（主键恒发、副键叠加，属行为变更）；模块级进程缓存加锁防竞态；复用窗口枚举回调，避免 GDI 对象泄漏。
- **logger**：日志文件句柄常驻，消除每秒约 20 次文件开关；写入异常降级，避免拖垮后台工作线程。
- **config**：字段自举（`asdict`）+ 版本号字段；解析失败时备份原文件；原子写避免半写损坏。
- **gui**：修复瞄准镜绘制中的裸 `except`；`psutil` 改为模块顶部导入；resize 增加宽度守卫避免全量重绘；修复图标按下/释放缩放浮点漂移；关闭时释放日志句柄并设置线程 join 超时。
- **main**：改用 DPI 感知新 API（`SetProcessDpiAwareness`），并对不支持的情况输出告警而非静默吞掉。
- **hotkey_manager**：轮询异常后仍能继续轮询；`_MOD_FLAGS` 重命名为 `MOD_FLAGS`。
- **新增 paths.py**：统一资源/基路径解析，消除各模块重复逻辑。

### 构建 (Build)
- 使用 PyInstaller 6.22.3（Python 3.11.9）重新编译 `dist/BBBus.exe`（窗口程序，已内嵌图标与 `config.json`）。

## [4.0.0] - 2026-08-11

### 新增 (Added)
- 初始发布：BBBus V4.0，Windows 平台工控/游戏自动化按键工具。
- 全局键盘热键（异步状态轮询）与鼠标侧键/滚轮热键（低层钩子 `WH_MOUSE_LL`）。
- 单窗体 tkinter UI：目标进程选择、主/副键配置、间隔设置、瞄准镜可视化、悬浮提示。
- 配置读写、进程枚举、日志开关。
