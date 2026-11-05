# -*- coding: utf-8 -*-
"""
持续监控并杀掉"描述（Description）含 Creative"的进程（常驻运行）。

典型目标：Adobe Creative Cloud 后台进程。任务管理器里它们的"描述"列是
"Creative Cloud Core Service"、"Creative Cloud Content Manager" 等，
对应 exe 为 Adobe Desktop Service、CCXProcess、AdobeIPCBroker、CCLibrary 等。

用法：
    python kill_creative.py            # 默认每 5 秒检查一次
    python kill_creative.py 2          # 每 2 秒检查一次
按 Ctrl+C 退出。
"""

import sys
import time
import json
import logging
import subprocess

# 匹配关键字（不区分大小写），进程的"描述"列包含它就会被杀掉
KEYWORD = "Creative"

# 默认检查间隔（秒）
DEFAULT_INTERVAL = 5

# powershell 启动时不弹出黑色窗口
CREATE_NO_WINDOW = 0x08000000

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("kill_creative")

# 一段 powershell：查描述含 KEYWORD 的进程 → 输出 JSON → 强杀
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
    """杀掉描述包含 KEYWORD 的进程，返回杀掉的进程数。"""
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

    out = result.stdout.strip()
    if not out:
        return 0  # 没有目标进程

    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        logger.warning("解析 powershell 输出失败: %s", out[:200])
        return 0

    # ConvertTo-Json 单个对象时返回 {}，多个时才返回 []，统一转成列表
    if isinstance(data, dict):
        data = [data]

    for p in data:
        logger.info(
            "已终止: pid=%s name=%s desc=%s",
            p.get("Id"), p.get("ProcessName"), p.get("Description"),
        )
    return len(data)


def main() -> None:
    interval = DEFAULT_INTERVAL
    if len(sys.argv) > 1:
        try:
            interval = max(1, float(sys.argv[1]))
        except ValueError:
            logger.warning("参数不是有效数字，使用默认间隔 %s 秒", DEFAULT_INTERVAL)

    logger.info("开始监控：描述列包含 '%s' 的进程将被杀掉，每 %s 秒检查一次", KEYWORD, interval)
    logger.info("按 Ctrl+C 退出")

    try:
        while True:
            n = kill_creative_processes()
            if n:
                logger.info("本轮共杀掉 %s 个进程", n)
            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("收到退出信号，程序结束")


if __name__ == "__main__":
    main()
