"""日志页：桥接 state/bridge.log 的只读尾巴（离线时降级提示）。"""

from __future__ import annotations

import control
from flask import Blueprint, render_template, request

from views.auth import login_required

bp = Blueprint("logs", __name__)


@bp.get("/logs")
@login_required
def index():
    lines = min(2000, max(50, int(request.args.get("lines", "200"))))
    error = None
    text = ""
    try:
        text = control.logs(lines).get("text", "")
    except control.BridgeError as exc:
        error = str(exc)
    return render_template("logs.html", text=text, lines=lines, error=error)
