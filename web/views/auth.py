"""登录与 JWT 鉴权。

安全模型（P1）：
- 密码：`kb_user.password_hash`（werkzeug PBKDF2，与既有 kb-admin 一致）。
- 会话：JWT 放 **HttpOnly Cookie**（SameSite=Lax，不设 Secure，因为明确只用 HTTP）。
- CSRF：JWT 里带一次性 `csrf`；所有写请求必须回传 `X-CSRF-Token` 或表单 `csrf` 字段。
- 限流：同一 IP 5 分钟内最多 N 次失败登录（内存计数，进程重启清零，够用）。
"""

from __future__ import annotations

import secrets
import time
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt

import captcha
import lockout
from flask import (
    Blueprint, g, make_response, redirect, render_template, request, url_for,
)

from db import query
from passwords import verify_password
from settings import settings

bp = Blueprint("auth", __name__)

_failures: dict[str, list[float]] = {}
RATE_WINDOW = 300


def _rate_hit(ip: str) -> bool:
    now = time.time()
    hits = [t for t in _failures.get(ip, []) if now - t < RATE_WINDOW]
    _failures[ip] = hits
    return len(hits) >= settings.login_rate_limit


def _rate_record(ip: str) -> None:
    _failures.setdefault(ip, []).append(time.time())


def _issue_token(user) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user["id"]),
        "name": user["username"],
        "role": user["role"],
        "csrf": secrets.token_urlsafe(24),
        "iat": now,
        "exp": now + timedelta(hours=settings.session_hours),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)


def current_claims():
    token = request.cookies.get(settings.cookie_name)
    if not token:
        return None
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])
    except jwt.PyJWTError:
        return None


def csrf_ok() -> bool:
    claims = getattr(g, "claims", None)
    if not claims:
        return False
    supplied = request.headers.get("X-CSRF-Token") or request.form.get("csrf") or ""
    return bool(supplied) and secrets.compare_digest(str(supplied), str(claims.get("csrf", "")))


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        claims = current_claims()
        if not claims:
            if request.path.startswith("/api/"):
                return {"ok": False, "error": "未登录"}, 401
            return redirect(url_for("auth.login", next=request.path))
        g.claims = claims
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and not csrf_ok():
            if request.path.startswith("/api/"):
                return {"ok": False, "error": "CSRF 校验失败"}, 403
            return render_template("error.html", message="CSRF 校验失败，请刷新页面后重试"), 403
        return view(*args, **kwargs)

    return wrapper


@bp.app_context_processor
def inject_identity():
    claims = getattr(g, "claims", None) or current_claims()
    return {"current_user": claims, "csrf_token": (claims or {}).get("csrf", "")}


@bp.get("/captcha")
def captcha_image():
    from flask import Response
    png = captcha.generate_captcha()
    return Response(png, mimetype="image/png", headers={"Cache-Control": "no-store"})


@bp.get("/login")
def login():
    if current_claims():
        return redirect(url_for("dashboard.index"))
    return render_template("login.html", next=request.args.get("next", ""), error=None)


@bp.post("/login")
def do_login():
    ip = (request.headers.get("X-Forwarded-For", request.remote_addr or "") or "").split(",")[0].strip()

    # 1) 封禁检查（内存态，重启后端重置）
    remaining = lockout.check(ip)
    if remaining > 0:
        minutes = max(1, (remaining + 59) // 60)
        return render_template("login.html", next="", error=f"登录失败次数过多，已封禁，请 {minutes} 分钟后再试"), 429

    # 2) 验证码（一次性）
    if not captcha.verify_captcha(request.form.get("captcha")):
        lock_seconds = lockout.fail(ip)
        if lock_seconds:
            return render_template("login.html", next="", error=f"验证码错误，且失败次数过多，已封禁 {lock_seconds // 60} 分钟"), 429
        return render_template("login.html", next="", error="验证码错误"), 401

    # 3) 账号密码（明文校验，不兼容旧哈希）
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    user = query("SELECT id, username, password_hash, role, enabled FROM kb_user WHERE username = %s", (username,), one=True)
    if not user or not user.get("enabled") or not verify_password(user["password_hash"], password):
        lock_seconds = lockout.fail(ip)
        if lock_seconds:
            minutes = max(1, lock_seconds // 60)
            return render_template("login.html", next="", error=f"用户名或密码错误，失败次数过多，已封禁 {minutes} 分钟"), 429
        return render_template("login.html", next="", error="用户名或密码错误"), 401

    lockout.reset(ip)
    token = _issue_token(user)
    target = request.form.get("next") or url_for("dashboard.index")
    if not target.startswith("/") or target.startswith("//"):
        target = url_for("dashboard.index")
    resp = make_response(redirect(target))
    resp.set_cookie(
        settings.cookie_name, token,
        max_age=settings.session_hours * 3600,
        httponly=True, samesite="Lax", secure=False, path="/",
    )
    return resp


@bp.post("/logout")
@login_required
def logout():
    resp = make_response(redirect(url_for("auth.login")))
    resp.delete_cookie(settings.cookie_name, path="/")
    return resp


@bp.get("/api/me")
@login_required
def me():
    return {"ok": True, "user": {"name": g.claims.get("name"), "role": g.claims.get("role")}}
