"""概览页：桥接状态 + 会话列表（P1 只读）。

桥接离线时页面照常渲染，只是状态卡片显示"离线"，不抛 500。
"""

from __future__ import annotations

import control
import usage
from flask import Blueprint, render_template, request

from views.auth import login_required

bp = Blueprint("dashboard", __name__)


def _collect():
    try:
        status = control.status()
        sessions = control.sessions().get("sessions", [])
        return status, sessions, None
    except control.BridgeError as exc:
        return None, [], str(exc)


@bp.get("/")
@login_required
def index():
    status, sessions, error = _collect()
    conv = (request.args.get("conv") or "").strip()
    scope = (request.args.get("scope") or "24h").strip()
    day = (request.args.get("day") or "").strip()
    usage_info = usage.collect(scope, day or None, conv)
    return render_template("dashboard.html", status=status, sessions=sessions, bridge_error=error, usage=usage_info)


@bp.get("/api/status")
@login_required
def api_status():
    status, sessions, error = _collect()
    if error:
        return {"ok": False, "error": error}, 503
    return {"ok": True, "status": status, "sessions": sessions}
