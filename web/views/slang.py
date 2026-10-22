"""黑话库页：列表 / 编辑 / 状态流转（候选↔确认/拒绝）/ 删除 / 触发 AI 学习。

数据表 kb_slang 由桥接作为权威（本地 state/slang.json 只是镜像）；这里的写入带
updated_ms，桥接按"谁更新更晚"合并，所以控制台改完最多 60s 生效。
"""

from __future__ import annotations

import time

import control
import kb_common
from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from db import execute, query
from views.auth import login_required

bp = Blueprint("slang", __name__)

STATUSES = ["candidate", "confirmed", "rejected"]


def _actor() -> str:
    claims = getattr(g, "claims", None) or {}
    return str(claims.get("name") or "console")


def _now_ms() -> int:
    return int(time.time() * 1000)


@bp.get("/slang")
@login_required
def index():
    status = (request.args.get("status") or "all").strip()
    q = (request.args.get("q") or "").strip()
    where, params = [], []
    if status in STATUSES:
        where.append("status = %s")
        params.append(status)
    if q:
        where.append("(content LIKE %s OR meaning LIKE %s OR `usage` LIKE %s)")
        params += [f"%{q}%"] * 3
    sql = "SELECT id, content, meaning, `usage`, example, risk, status, source, `count`, updated_at FROM kb_slang"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY FIELD(status,'candidate','confirmed','rejected'), `count` DESC, updated_at DESC LIMIT 300"
    rows = query(sql, tuple(params))
    counts = {row["status"]: row["n"] for row in query("SELECT status, COUNT(*) AS n FROM kb_slang GROUP BY status")}
    return render_template("slang_list.html", rows=rows, status=status, q=q, counts=counts)


@bp.route("/slang/<sid>/edit", methods=["GET", "POST"])
@login_required
def edit(sid: str):
    row = query("SELECT * FROM kb_slang WHERE id = %s", (sid,), one=True)
    if not row:
        flash("黑话不存在", "error")
        return redirect(url_for("slang.index"))
    if request.method == "POST":
        payload = {
            "content": (request.form.get("content") or "").strip()[:64],
            "meaning": (request.form.get("meaning") or "").strip()[:255],
            "usage": (request.form.get("usage") or "").strip()[:255],
            "example": (request.form.get("example") or "").strip()[:255],
            "risk": (request.form.get("risk") or "").strip()[:255],
            "status": request.form.get("status") if request.form.get("status") in STATUSES else row["status"],
        }
        if not payload["content"]:
            flash("词条不能为空", "error")
            return render_template("slang_edit.html", row={**row, **payload}, statuses=STATUSES)
        execute(
            "UPDATE kb_slang SET content = %s, meaning = %s, `usage` = %s, example = %s, risk = %s, status = %s, updated_ms = %s WHERE id = %s",
            (payload["content"], payload["meaning"], payload["usage"], payload["example"], payload["risk"], payload["status"], _now_ms(), sid),
        )
        kb_common.log_slang_revision(sid, "update", payload["content"], row, payload, _actor())
        flash("已保存（桥接 60s 内同步）", "ok")
        return redirect(url_for("slang.index"))
    return render_template("slang_edit.html", row=row, statuses=STATUSES)


@bp.post("/slang/<sid>/status")
@login_required
def set_status(sid: str):
    target = request.form.get("status")
    if target not in STATUSES:
        flash("非法状态", "error")
        return redirect(url_for("slang.index"))
    row = query("SELECT * FROM kb_slang WHERE id = %s", (sid,), one=True)
    if not row:
        flash("黑话不存在", "error")
        return redirect(url_for("slang.index"))
    execute("UPDATE kb_slang SET status = %s, updated_ms = %s WHERE id = %s", (target, _now_ms(), sid))
    kb_common.log_slang_revision(sid, {"confirmed": "confirm", "rejected": "reject", "candidate": "candidate"}[target],
                                 row["content"], row, {**row, "status": target}, _actor())
    flash(f"「{row['content']}」→ {target}", "ok")
    return redirect(url_for("slang.index", status=request.form.get("back") or "all"))


@bp.post("/slang/<sid>/delete")
@login_required
def delete(sid: str):
    row = query("SELECT * FROM kb_slang WHERE id = %s", (sid,), one=True)
    if not row:
        flash("黑话不存在", "error")
        return redirect(url_for("slang.index"))
    execute("DELETE FROM kb_slang WHERE id = %s", (sid,))
    kb_common.log_slang_revision(sid, "delete", row["content"], row, None, _actor())
    flash(f"已删除「{row['content']}」", "ok")
    return redirect(url_for("slang.index"))


@bp.post("/slang/learn")
@login_required
def learn():
    mode = request.form.get("mode") or "extract"
    path = "/api/slang/extract" if mode == "extract" else "/api/slang/research"
    try:
        result = control.admin_post(path, {})
    except control.BridgeError as exc:
        flash(f"触发学习失败：{exc}（桥接没在跑？）", "error")
        return redirect(url_for("slang.index"))
    if result.get("ok"):
        detail = f"key={result.get('key')}" if result.get("key") else f"候选 {result.get('count', '?')} 条"
        flash(f"已触发{'抽取' if mode == 'extract' else '研究'}（{detail}），结果稍后出现在候选里", "ok")
    else:
        flash(f"触发失败：{result.get('error') or result}", "error")
    return redirect(url_for("slang.index"))
