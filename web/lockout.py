"""按 IP 的登录失败封禁（内存态，**重启后端即重置**）。

规则（按用户要求）：
- 连续失败 3 次 → 封 10 分钟；
- 解封后再次连续失败 3 次 → 封 1 小时；
- 之后每再累计 3 次失败，封禁时长 +1 小时（2h、3h…）；
- 登录成功清零该 IP 的失败计数与等级；
- 状态只在内存里：进程重启即全部重置。

实现要点：`check()` 返回剩余封禁秒数；`fail()` 记一次失败并在达到阈值时开始封禁。
"""

from __future__ import annotations

import time

_WINDOW_FAILS: dict[str, int] = {}
_LEVEL: dict[str, int] = {}
_LOCK_UNTIL: dict[str, float] = {}


def _duration(level: int) -> int:
    """level 1 → 10 分钟；level 2 → 1 小时；level N>=3 → N-1 小时。"""
    if level <= 1:
        return 10 * 60
    return (level - 1) * 3600


def check(ip: str) -> int:
    """返回剩余封禁秒数（0 = 未封禁）。"""
    until = _LOCK_UNTIL.get(ip, 0)
    remaining = int(until - time.time())
    if remaining <= 0:
        if until:
            _LOCK_UNTIL.pop(ip, None)
        return 0
    return remaining


def fail(ip: str) -> int:
    """记录一次失败；若触发封禁返回封禁秒数，否则返回 0。"""
    _WINDOW_FAILS[ip] = _WINDOW_FAILS.get(ip, 0) + 1
    if _WINDOW_FAILS[ip] % 3 != 0:
        return 0
    level = _LEVEL.get(ip, 0) + 1
    _LEVEL[ip] = level
    duration = _duration(level)
    _LOCK_UNTIL[ip] = time.time() + duration
    return duration


def reset(ip: str) -> None:
    _WINDOW_FAILS.pop(ip, None)
    _LEVEL.pop(ip, None)
    _LOCK_UNTIL.pop(ip, None)


def describe(ip: str) -> dict:
    return {
        "fails": _WINDOW_FAILS.get(ip, 0),
        "level": _LEVEL.get(ip, 0),
        "remaining": check(ip),
    }
