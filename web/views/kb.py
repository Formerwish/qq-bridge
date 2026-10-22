"""知识库条目页：列表 / 新建 / 编辑 / 启停 / 删除 / 注入预览 / 修订记录。

直接把数据写进 MySQL（与桥接共用同一张 kb_entry 表）；桥接侧的 KB 客户端每 60s 刷新一次，
所以这里的改动会在一个刷新周期内被下一条唤醒看到（无需重启）。
"""

from __future__ import annotations

import kb_common
from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from db import execute, insert, query
from views.auth import login_required

bp = Blueprint("kb", __name__)

MAX_TITLE = 128
MAX_KEYWORDS = 255
MAX_BODY = 20000


def _actor() -> str:
    claims = getattr(g, "claims", None) or {}
    return str(claims.get("name") or "console")


def _form_payload():
    return {
        "topic": (request.form.get("topic") or "第五人格").strip()[:32] or "第五人格",
        "title": (request.form.get("title") or "").strip()[:MAX_TITLE],
        "keywords": (request.form.get("keywords") or "").strip()[:MAX_KEYWORDS],
        "body": (request.form.get("body") or "").strip()[:MAX_BODY],
        "priority": int(request.form.get("priority") or 0) if str(request.form.get("priority") or "0").lstrip("-").isdigit() else 0,
        "enabled": 1 if request.form.get("enabled") in {"on", "1", "true"} else 0,
    }


def _validate(payload: dict) -> str | None:
    if not payload["title"]:
        return "标题不能为空"
    if not payload["body"]:
        return "正文不能为空"
    if not kb_common.split_keywords(payload["keywords"]):
        return "关键词不能为空（逗号/顿号/空格分隔）"
    return None


@bp.get("/kb")
@login_required
def index():
    q = (request.args.get("q") or "").strip()
    topic = (request.args.get("topic") or "").strip()
    where, params = [], []
    if q:
        where.append("(title LIKE %s OR keywords LIKE %s OR body LIKE %s)")
        params += [f"%{q}%"] * 3
    if topic:
        where.append("topic = %s")
        params.append(topic)
    sql = "SELECT id, topic, title, keywords, priority, enabled, updated_by, updated_at FROM kb_entry"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY priority DESC, updated_at DESC LIMIT 300"
    rows = query(sql, tuple(params))
    topics = [item["topic"] for item in query("SELECT DISTINCT topic FROM kb_entry ORDER BY topic")]
    return render_template("kb_list.html", rows=rows, q=q, topic=topic, topics=topics)


@bp.route("/kb/new", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "POST":
        payload = _form_payload()
        error = _validate(payload)
        if error:
            flash(error, "error")
            return render_template("kb_edit.html", entry=payload, mode="new")
        entry_id = insert(
            "INSERT INTO kb_entry (topic, title, keywords, body, priority, enabled, created_by, updated_by) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (payload["topic"], payload["title"], payload["keywords"], payload["body"], payload["priority"], payload["enabled"], _actor(), _actor()),
        )
        kb_common.log_entry_revision(entry_id, "create", payload["title"], None, payload, _actor())
        flash("已创建条目", "ok")
        return redirect(url_for("kb.index"))
    return render_template("kb_edit.html", entry={"topic": "第五人格", "enabled": 1, "priority": 0}, mode="new")


@bp.route("/kb/<int:entry_id>/edit", methods=["GET", "POST"])
@login_required
def edit(entry_id: int):
    entry = query("SELECT * FROM kb_entry WHERE id = %s", (entry_id,), one=True)
    if not entry:
        flash("条目不存在", "error")
        return redirect(url_for("kb.index"))
    if request.method == "POST":
        payload = _form_payload()
        error = _validate(payload)
        if error:
            flash(error, "error")
            return render_template("kb_edit.html", entry={**entry, **payload}, mode="edit")
        execute(
            "UPDATE kb_entry SET topic = %s, title = %s, keywords = %s, body = %s, priority = %s, enabled = %s, updated_by = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (payload["topic"], payload["title"], payload["keywords"], payload["body"], payload["priority"], payload["enabled"], _actor(), entry_id),
        )
        kb_common.log_entry_revision(entry_id, "update", payload["title"], entry, payload, _actor())
        flash("已保存", "ok")
        return redirect(url_for("kb.index"))
    return render_template("kb_edit.html", entry=entry, mode="edit")


@bp.post("/kb/<int:entry_id>/toggle")
@login_required
def toggle(entry_id: int):
    entry = query("SELECT * FROM kb_entry WHERE id = %s", (entry_id,), one=True)
    if not entry:
        flash("条目不存在", "error")
        return redirect(url_for("kb.index"))
    enabled = 0 if entry["enabled"] else 1
    execute("UPDATE kb_entry SET enabled = %s, updated_by = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (enabled, _actor(), entry_id))
    kb_common.log_entry_revision(entry_id, "enable" if enabled else "disable", entry["title"], entry, {**entry, "enabled": enabled}, _actor())
    flash("已启用" if enabled else "已停用", "ok")
    return redirect(url_for("kb.index"))


@bp.post("/kb/<int:entry_id>/delete")
@login_required
def delete(entry_id: int):
    entry = query("SELECT * FROM kb_entry WHERE id = %s", (entry_id,), one=True)
    if not entry:
        flash("条目不存在", "error")
        return redirect(url_for("kb.index"))
    execute("DELETE FROM kb_entry WHERE id = %s", (entry_id,))
    kb_common.log_entry_revision(entry_id, "delete", entry["title"], entry, None, _actor())
    flash(f"已删除「{entry['title']}」", "ok")
    return redirect(url_for("kb.index"))


@bp.route("/kb/preview", methods=["GET", "POST"])
@login_required
def preview():
    text = (request.form.get("text") or request.args.get("text") or "").strip()
    max_entries, max_chars = kb_common.inject_limits()
    matched, block = [], ""
    if text:
        rows = query("SELECT id, topic, title, keywords, body, priority FROM kb_entry WHERE enabled = 1")
        matched = kb_common.match_entries(rows, text, max_entries)
        block = kb_common.build_injection_block(matched, max_chars)
    return render_template("kb_preview.html", text=text, matched=matched, block=block,
                           max_entries=max_entries, max_chars=max_chars)


@bp.get("/revisions")
@login_required
def revisions():
    rows = query(
        "SELECT r.id, r.entry_id, r.action, r.title, r.actor, r.created_at, e.title AS current_title "
        "FROM kb_revision r LEFT JOIN kb_entry e ON e.id = r.entry_id ORDER BY r.id DESC LIMIT 200"
    )
    slang_rows = query(
        "SELECT id, slang_id, action, content, actor, created_at FROM kb_slang_revision ORDER BY id DESC LIMIT 200"
    )
    return render_template("revisions.html", rows=rows, slang_rows=slang_rows)
