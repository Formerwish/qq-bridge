"""用户管理：列表 / 新建 / 重置密码 / 启停（仅 admin）。

用户表沿用 kb_user（werkzeug PBKDF2），与旧 kb-admin 完全兼容。
"""

from __future__ import annotations

import secrets
import string
from functools import wraps

import kb_common
from passwords import display_password, make_password
from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from db import execute, insert, query
from views.auth import login_required

bp = Blueprint("users", __name__)

MIN_PASSWORD = 8


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapper(*args, **kwargs):
        claims = getattr(g, "claims", None) or {}
        if claims.get("role") != "admin":
            flash("需要管理员权限", "error")
            return redirect(url_for("dashboard.index"))
        return view(*args, **kwargs)

    return wrapper


def _actor() -> str:
    return str((getattr(g, "claims", None) or {}).get("name") or "console")


def _random_password(length: int = 14) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


@bp.get("/users")
@admin_required
def index():
    rows = query("SELECT id, username, role, enabled, created_by, created_at, last_login_at, password_hash FROM kb_user ORDER BY id")
    for row in rows:
        row["plain_password"] = display_password(row.get("password_hash"))
    return render_template("users.html", rows=rows)


@bp.post("/users")
@admin_required
def create():
    username = (request.form.get("username") or "").strip()[:64]
    role = request.form.get("role") if request.form.get("role") in {"admin", "editor"} else "editor"
    password = request.form.get("password") or ""
    if not username:
        flash("用户名不能为空", "error")
        return redirect(url_for("users.index"))
    if len(password) < MIN_PASSWORD:
        flash(f"密码至少 {MIN_PASSWORD} 位", "error")
        return redirect(url_for("users.index"))
    if query("SELECT id FROM kb_user WHERE username = %s", (username,), one=True):
        flash("用户名已存在", "error")
        return redirect(url_for("users.index"))
    insert(
        "INSERT INTO kb_user (username, password_hash, role, enabled, created_by) VALUES (%s, %s, %s, 1, %s)",
        (username, make_password(password), role, _actor()),
    )
    flash(f"已创建用户 {username}（{role}）", "ok")
    return redirect(url_for("users.index"))


@bp.post("/users/<int:user_id>/password")
@admin_required
def reset_password(user_id: int):
    row = query("SELECT id, username FROM kb_user WHERE id = %s", (user_id,), one=True)
    if not row:
        flash("用户不存在", "error")
        return redirect(url_for("users.index"))
    password = (request.form.get("password") or "").strip()
    generated = False
    if not password:
        password = _random_password()
        generated = True
    if len(password) < MIN_PASSWORD:
        flash(f"密码至少 {MIN_PASSWORD} 位", "error")
        return redirect(url_for("users.index"))
    execute("UPDATE kb_user SET password_hash = %s WHERE id = %s", (make_password(password), user_id))
    flash(f"{row['username']} 的新密码：{password}" + ("（自动生成，请立即保存）" if generated else ""), "ok")
    return redirect(url_for("users.index"))


@bp.post("/users/<int:user_id>/toggle")
@admin_required
def toggle(user_id: int):
    row = query("SELECT id, username, enabled FROM kb_user WHERE id = %s", (user_id,), one=True)
    if not row:
        flash("用户不存在", "error")
        return redirect(url_for("users.index"))
    if row["username"] == _actor():
        flash("不能停用当前登录用户", "error")
        return redirect(url_for("users.index"))
    enabled = 0 if row["enabled"] else 1
    execute("UPDATE kb_user SET enabled = %s WHERE id = %s", (enabled, user_id))
    flash(f"{row['username']} 已{'启用' if enabled else '停用'}", "ok")
    return redirect(url_for("users.index"))
