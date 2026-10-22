"""设置页：白名单 / owner / 会话时长（热更新，无需重启）。"""

from __future__ import annotations

import control
from flask import Blueprint, flash, redirect, render_template, request, url_for

from views.auth import login_required

bp = Blueprint("settings", __name__)


def _ids(text: str) -> list[int]:
    """逗号/空格/换行分隔的 QQ 号 → 去重整数列表。"""
    seen: list[int] = []
    for part in str(text or "").replace("\n", ",").replace(" ", ",").split(","):
        part = part.strip()
        if not part:
            continue
        if not part.isdigit():
            raise ValueError(f"不是有效的 QQ 号：{part}")
        num = int(part)
        if num not in seen:
            seen.append(num)
    return seen


def _join(values) -> str:
    return ", ".join(str(v) for v in values or [])


@bp.get("/settings")
@login_required
def index():
    error = None
    info = None
    try:
        info = control.config_get()
    except control.BridgeError as exc:
        error = str(exc)
    return render_template("settings.html", info=info, error=error)


@bp.post("/settings")
@login_required
def save():
    try:
        updates = {
            "allow.groups": _ids(request.form.get("allow_groups", "")),
            "allow.private": _ids(request.form.get("allow_private", "")),
            "deny.groups": _ids(request.form.get("deny_groups", "")),
            "deny.private": _ids(request.form.get("deny_private", "")),
            "ownerQQ": int(request.form.get("owner_qq", "0") or 0),
            "web.sessionHours": int(request.form.get("session_hours", "8") or 8),
        }
        control.config_update(updates)
        flash("设置已保存并热更新（白名单立即生效，无需重启）", "ok")
    except (ValueError, control.BridgeError) as exc:
        flash(f"保存失败：{exc}", "error")
    return redirect(url_for("settings.index"))
