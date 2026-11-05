# -*- coding: utf-8 -*-
"""
Creative Guard —— 后台常驻程序

持续监控并杀掉"描述含 Creative"的 Adobe 进程
（任务管理器里显示为 Creative Cloud Core Service / Creative Cloud Content Manager 等）。

功能：
  1. 开机自动启动（启动文件夹里已放置快捷方式）
  2. 全局热键 Ctrl+Alt+` 开启 / 关闭监控（程序本身不退出）
     提示音：高音两声 = 已开启，低音一声 = 已关闭
  3. 运行日志：creative_guard.log（与本文件同目录）

说明：启动后默认处于"监控开启"状态。关闭监控后程序仍在后台待命，
按热键即可重新开启。要彻底退出，在任务管理器里结束 pythonw.exe。
"""

import ctypes
import json
import logging
import os
import subprocess
import sys
import threading
import time
import winsound
from ctypes import wintypes

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "creative_guard.log")

KEYWORD = "Creative"    # 进程描述里包含这个词就会被杀掉
CHECK_INTERVAL = 3      # 监控检查间隔（秒）
CREATE_NO_WINDOW = 0x08000000

# ---- 全局热键：Ctrl + Alt + `（反引号键，键盘左上角 Esc 下面）----
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
VK_OEM_3 = 0xC0         # 反引号 ` 键的虚拟键码
HOTKEY_ID = 1
WM_HOTKEY = 0x0312

# 日志配置：pythonw 没有控制台，只有在有 stderr 时才同时输出到屏幕
_log_handlers = [logging.FileHandler(LOG_FILE, encoding="utf-8")]
if sys.stderr is not None:
    _log_handlers.append(logging.StreamHandler())

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=_log_handlers,
)
logger = logging.getLogger("creative_guard")

# 监控开关：set = 正在监控，clear = 暂停监控
monitor_on = threading.Event()
monitor_on.set()   # 默认开机即监控

# 查询并杀掉描述含 KEYWORD 的进程（先输出信息，再强杀）
PS_SCRIPT = (
    "[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
    "$p = Get-Process -ErrorAction SilentlyContinue | "
    "Where-Object {$_.Description -like '*" + KEYWORD + "*'}; "
    "if ($p) { "
    "$info = $p | Select-Object Id,ProcessName,Description; "
    "$info | ConvertTo-Json -Compress; "
    "$p | Stop-Process -Force -ErrorAction SilentlyContinue "
    "}"
)


def kill_creative_processes() -> int:
    """查询并杀掉描述含 KEYWORD 的进程，返回本轮杀掉的数量。"""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", PS_SCRIPT],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=CREATE_NO_WINDOW,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        logger.error("powershell 查询超时")
        return 0
    except Exception:
        logger.exception("调用 powershell 失败")
        return 0

    out = result.stdout.strip()
    if not out:
        return 0  # 没有目标进程

    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        logger.warning("解析 powershell 输出失败: %s", out[:200])
        return 0

    # ConvertTo-Json 单个对象时返回 {}，多个时才返回 []
    if isinstance(data, dict):
        data = [data]

    for p in data:
        logger.info(
            "已终止: pid=%s name=%s desc=%s",
            p.get("Id"), p.get("ProcessName"), p.get("Description"),
        )
    return len(data)


def monitor_loop() -> None:
    """后台监控线程：监控开启时每 CHECK_INTERVAL 秒扫描一次。"""
    while True:
        if monitor_on.is_set():
            try:
                n = kill_creative_processes()
                if n:
                    logger.info("本轮共杀掉 %s 个进程", n)
            except Exception:
                logger.exception("监控循环出错")
        time.sleep(CHECK_INTERVAL)


def toggle_monitor() -> None:
    """切换监控开关，并用不同音调提示当前状态。"""
    if monitor_on.is_set():
        monitor_on.clear()
        winsound.Beep(500, 200)      # 低音一声 = 已关闭
        logger.info("监控已关闭（再按一次 Ctrl+Alt+` 开启）")
    else:
        monitor_on.set()
        winsound.Beep(1000, 120)     # 高音两声 = 已开启
        winsound.Beep(1300, 120)
        logger.info("监控已开启")


def acquire_single_instance():
    """互斥体防止重复启动。成功返回句柄，已有实例在跑则返回 None。"""
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateMutexW(None, False, "CreativeGuardMutex")
    if kernel32.GetLastError() == 183:   # ERROR_ALREADY_EXISTS
        return None
    return handle


def run_hotkey_loop() -> None:
    """主线程：注册全局热键并等待按键消息。"""
    user32 = ctypes.windll.user32
    if not user32.RegisterHotKey(None, HOTKEY_ID, MOD_CONTROL | MOD_ALT, VK_OEM_3):
        logger.error("热键 Ctrl+Alt+` 注册失败（可能被其他程序占用），热键将不可用")
        # 热键不可用时依然保持后台监控，只是没法用键盘切换
        while True:
            time.sleep(3600)
    logger.info("全局热键已注册：Ctrl+Alt+` 开启/关闭监控")

    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
            toggle_monitor()
    user32.UnregisterHotKey(None, HOTKEY_ID)


def main() -> None:
    mutex = acquire_single_instance()
    if mutex is None:
        logger.warning("检测到程序已在运行，本次启动取消")
        return

    logger.info("=" * 55)
    logger.info("Creative Guard 启动，监控状态：开启")
    threading.Thread(target=monitor_loop, daemon=True).start()
    run_hotkey_loop()


if __name__ == "__main__":
    main()
