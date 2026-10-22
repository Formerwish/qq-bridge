"""会话页：列表 + 详情 + 管理动作（暂停、标记已读、唤醒配置）。

所有动作走桥接 `/internal/*`；桥接离线时页面降级为只读并给出错误提示。
"""

from __future__ import annotations

import control
from flask import Blueprint, flash, redirect, render_template, request, url_for

from views.auth import login_required

bp = Blueprint("sessions", __name__)


def _int(form, name, default=None):
    raw = (form.get(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@bp.get("/sessions")
@login_required
def index():
    error = None
    sessions: list = []
    detail = None
    selected = (request.args.get("key") or "").strip()
    try:
        sessions = control.sessions().get("sessions", [])
        if selected:
            detail = control.session(selected)
    except control.BridgeError as exc:
        error = str(exc)
    return render_template("sessions.html", sessions=sessions, detail=detail, selected=selected, error=error)


@bp.post("/pause")
@login_required
def toggle_pause():
    want = request.form.get("paused") == "1"
    try:
        control.pause(want)
        flash("AI 已暂停（所有定时器已停止）" if want else "AI 已恢复", "ok")
    except control.BridgeError as exc:
        flash(f"操作失败：{exc}", "error")
    return redirect(request.form.get("back") or url_for("sessions.index"))


@bp.post("/sessions/<path:key>/mark-read")
@login_required
def mark_read(key: str):
    try:
        result = control.mark_read(key)
        flash(f"已标记已读：清掉 {result.get('marked', 0)} 条未读", "ok")
    except control.BridgeError as exc:
        flash(f"标记已读失败：{exc}", "error")
    return redirect(url_for("sessions.index", key=key))


@bp.post("/sessions/<path:key>/wake")
@login_required
def update_wake(key: str):
    form = request.form
    keywords = [k.strip() for k in (form.get("keywords") or "").replace("，", ",").split(",") if k.strip()]
    triggers = {
        "atMention": form.get("atMention") == "on",
        "nameMention": form.get("nameMention") == "on",
        "question": form.get("question") == "on",
        "poke": form.get("poke") == "on",
        "anyMessage": form.get("anyMessage") == "on",
    }
    pct = _int(form, "probability", 5)
    config: dict = {
        "mode": form.get("mode") or "diving",
        "triggers": {**triggers, "keywords": keywords, "probability": max(0, min(100, pct)) / 100.0},
    }
    batch = _int(form, "batchWindowMs", None)
    if batch:
        config["batchWindowMs"] = batch
    try:
        control.set_wake(key, config)
        flash("唤醒配置已更新（confirmedBy=console，不再跟随全局默认值）", "ok")
    except control.BridgeError as exc:
        flash(f"更新唤醒配置失败：{exc}", "error")
    return redirect(url_for("sessions.index", key=key))


@bp.post("/sessions/<path:key>/reset")
@login_required
def reset_session(key: str):
    try:
        control.reset_session(key)
        flash(f"{key} 已重置：下一条消息会从 DSH 新建会话（原上下文不再带入）", "ok")
    except control.BridgeError as exc:
        flash(f"重置失败：{exc}", "error")
    return redirect(url_for("sessions.index", key=key))
