"""人格卡页：列出 roles/*.md、编辑内容、切换当前人格。

桥接每条消息都会重新注入人格卡，所以保存即生效（无需重启）。
"""

from __future__ import annotations

import control
from flask import Blueprint, flash, redirect, render_template, request, url_for

from views.auth import login_required

bp = Blueprint("roles", __name__)


@bp.get("/roles")
@login_required
def index():
    error = None
    info = None
    detail = None
    name = (request.args.get("name") or "").strip()
    try:
        info = control.roles()
        if name:
            detail = control.role(name)
        elif info.get("current"):
            detail = control.role(info["current"])
    except control.BridgeError as exc:
        error = str(exc)
    return render_template("roles.html", info=info, detail=detail, error=error, name=name)


@bp.post("/roles/save")
@login_required
def save():
    name = (request.form.get("name") or "").strip()
    content = request.form.get("content") or ""
    try:
        result = control.save_role(name, content)
        flash(f"已保存 {result.get('name')}（{result.get('chars', 0)} 字），下一条消息生效", "ok")
    except control.BridgeError as exc:
        flash(f"保存失败：{exc}", "error")
    return redirect(url_for("roles.index", name=name))


@bp.post("/roles/current")
@login_required
def set_current():
    name = (request.form.get("name") or "").strip()
    try:
        control.set_current_role(name)
        flash(f"当前人格已切换为 {name}", "ok")
    except control.BridgeError as exc:
        flash(f"切换失败：{exc}", "error")
    return redirect(url_for("roles.index", name=name))
