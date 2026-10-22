"""日志：控制台（看得见）+ 文件（可回溯）。

- 控制台：Flask/werkzeug 的访问日志与错误会直接打在窗口里（用 web\\run.bat 启动时）；
- 文件：同时写 state/web.log（RotatingFileHandler，5MB × 3），后台启动也能排障；
- 统一格式：`YYYY-MM-DD HH:MM:SS LEVEL message`。
"""

from __future__ import annotations

import sys

import logging
from logging.handlers import RotatingFileHandler

from settings import STATE_DIR


def setup_logging(level: int = logging.INFO) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    # pythonw 启动时没有 stderr，挂 StreamHandler 会在写日志时抛异常。
    console = logging.StreamHandler() if sys.stderr is not None else None
    if console is not None:
        console.setFormatter(fmt)

    # 文件日志失败不能拖垮启动（Windows 上旧进程可能短暂占用 web.log）。
    try:
        file_handler = RotatingFileHandler(
            STATE_DIR / "web-console.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(fmt)
    except (PermissionError, OSError) as exc:
        print(f"[web] 警告：无法写 state/web.log（{exc}），仅输出到控制台。")
        file_handler = None

    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        root.removeHandler(handler)
    if console is not None:
        root.addHandler(console)
    if file_handler is not None:
        root.addHandler(file_handler)

    # werkzeug 的请求日志默认走自己的 logger，且不向 root 传播；显式接管。
    werkzeug = logging.getLogger("werkzeug")
    werkzeug.setLevel(level)
    werkzeug.handlers = ([console] if console is not None else []) + ([file_handler] if file_handler is not None else [])
    werkzeug.propagate = False
