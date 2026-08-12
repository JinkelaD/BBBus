# BBBus

**BBBus** 是一款运行在 Windows 上的轻量级自动化按键工具。它通过后台轮询向指定目标进程发送虚拟按键，支持随机间隔、副键输出、全局快捷键（键盘组合 / 鼠标侧键 / 滚轮）等能力，并提供一个紧凑的 tkinter 图形界面。

> ⚠️ 仅支持 **Windows** 平台（依赖 `ctypes` 调用 Windows API 与底层钩子）。

---

## ✨ 功能特性

- **目标进程锁定**：按「进程名」自动匹配，或手动填写「PID」精确定位。
- **键盘 / 鼠标注入**：向目标窗口投递虚拟按键（基于 Windows 消息 / `SendInput`）。
- **随机间隔**：在「间隔下限 / 上限」之间随机抖动，模拟更自然的节奏。
- **副输出键**：可设置第二按键（如切换状态）并按独立间隔周期发送。
- **全局快捷键**：一键启停，**支持键盘组合、鼠标侧键、滚轮及混合组合**，例如：
  - 键盘：`ctrl+shift+k`、`alt+f2`
  - 鼠标侧键：`mb4` / `mb5`
  - 鼠标滚轮：`wheel_up` / `wheel_down`
  - 混合：`ctrl+mb4`
  - 为**避免误触**，全局热键仅在主窗口「置顶」状态下生效。
- **进程浏览**：`☰` 按钮打开进程列表，按名称搜索并一键填入。
- **窗口瞄准**：`⊙` 按钮进入瞄准模式，用鼠标点选目标窗口自动获取其 PID / 标题。
- **置顶 / 日志开关**：主窗口可置顶常驻；日志开关开启后输出运行记录。
- **紧凑 UI**：240×560 的小窗体，配置卡片 + 启停按钮 + 状态栏。

---

## 📦 环境要求

- Windows 10 / 11
- Python 3.10+
- 依赖：`psutil`（GUI 与进程枚举使用标准库 `tkinter`）

---

## 🚀 从源码运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动
python main.py
```

首次运行会在程序同目录生成 `config.json` 保存你的配置。

---

## 🔧 打包为可执行文件

项目使用 [PyInstaller](https://pyinstaller.org/) 打包为单文件 exe：

```bash
pip install pyinstaller

pyinstaller --onefile --noconsole --name BBBus ^
    --icon icon/bbbus_icon.ico ^
    --add-data "icon/bbbus_icon.ico;icon" ^
    main.py
```

构建产物位于 `dist/BBBus.exe`。

> **注意（单文件模式）**：冻结后 `config.json` 的读取路径为 exe 同目录（`sys.executable` 所在目录）。若需携带默认配置，请将 `config.json` 与生成的 `BBBus.exe` 放在同一文件夹。

---

## ⚙️ 配置说明（`config.json`）

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `name` | string | `""` | 目标进程名（如 `notepad.exe`），空则按 PID |
| `pid` | int | `0` | 目标进程 PID，`0` 表示按名称自动匹配 |
| `target_key` | string | `"f1"` | 主输出按键（vk 名称，如 `f1`、`a`、`space`） |
| `interval_min` | int | `50` | 最小间隔（毫秒） |
| `interval_max` | int | `950` | 最大间隔（毫秒） |
| `sub_key` | string | `""` | 副输出按键，空则禁用 |
| `sub_key_interval` | int | `5000` | 副键发送间隔（毫秒） |
| `hotkey` | string | `"ctrl+shift+k"` | 全局启停热键（见上方语法） |
| `topmost` | bool | `false` | 主窗口是否置顶（同时决定全局热键是否生效） |
| `log_enabled` | bool | `false` | 是否输出日志 |

---

## ⌨️ 快捷键语法

在「快速热键」输入框填写，多个修饰键用 `+` 连接：

- 修饰键：`ctrl` / `alt` / `shift` / `win`
- 普通键：`a`~`z`、`0`~`9`、`f1`~`f12`、`space`、`enter`、`tab` 等 vk 名称
- 鼠标：`mb4`、`mb5`（侧键）、`wheel_up`、`wheel_down`（滚轮）
- 示例：`ctrl+shift+k`、`alt+f2`、`ctrl+mb4`、`wheel_down`

修改后点击其它位置（失焦）即立即生效；关闭「置顶」后热键自动停用。

---

## 📁 项目结构

```
BBBus/
├── main.py            # 程序入口
├── config.py          # 配置读写（AppConfig + config.json）
├── gui.py             # tkinter 界面与交互
├── key_worker.py      # 后台按键发送线程
├── hotkey_manager.py  # 全局热键（键盘轮询 + 鼠标底层钩子）
├── vk_map.py          # 虚拟键名 → vk 码映射（含鼠标键）
├── logger.py          # 日志工具
├── requirements.txt   # 依赖
├── icon/              # 程序图标
└── preview/           # 界面预览（可选）
```

---

## 📝 说明

- 本工具仅用于合法、合规的自动化场景（如游戏辅助、重复操作减负），请勿用于违反软件服务条款或法律法规的用途。
- 全局热键依赖 Windows 底层钩子，部分安全软件可能拦截；如热键无响应请检查杀毒 / 防火墙白名单。
