"""表情库页：查看收藏表情、改自己的备注/标签、手动同步。

桥接是表情库的唯一写入方（内存 + state/stickers.json 直写），所以这里走
/internal/stickers*，不直接改文件。
"""

from __future__ import annotations

import control
import hashlib
import io

from flask import Blueprint, flash, redirect, render_template, request, send_file, url_for

from settings import STATE_DIR
from views.auth import login_required

bp = Blueprint("stickers", __name__)


@bp.get("/stickers")
@login_required
def index():
    error = None
    data = {"entries": [], "count": 0}
    q = (request.args.get("q") or "").strip().lower()
    try:
        data = control.stickers()
    except control.BridgeError as exc:
        error = str(exc)
    rows = data.get("entries") or []
    if (request.args.get("fav") or "") == "1":
        rows = [r for r in rows if r.get("favorite")]
    if q:
        rows = [r for r in rows if q in (r.get("localNote") or "").lower()
                or q in (r.get("desc") or "").lower()
                or any(q in str(t).lower() for t in (r.get("tags") or []))]
    rows.sort(key=lambda r: (not r.get("favorite"), -(r.get("useCount") or 0), r.get("id") or ""))
    return render_template("stickers.html", rows=rows, total=data.get("count", 0), error=error, q=q, fav=(request.args.get("fav") or ""))


@bp.post("/stickers/note")
@login_required
def save_note():
    sticker_id = (request.form.get("id") or "").strip()
    note = (request.form.get("localNote") or "").strip()[:200]
    tags = [t.strip() for t in (request.form.get("tags") or "").replace("，", ",").split(",") if t.strip()][:12]
    try:
        control.sticker_note(sticker_id, note, tags)
        flash(f"已更新 {sticker_id}", "ok")
    except control.BridgeError as exc:
        flash(f"更新失败：{exc}", "error")
    return redirect(url_for("stickers.index"))


@bp.post("/stickers/sync")
@login_required
def sync():
    try:
        result = control.sticker_sync()
        flash(f"已同步，当前 {result.get('count', '?')} 个收藏表情", "ok")
    except control.BridgeError as exc:
        flash(f"同步失败：{exc}", "error")
    return redirect(url_for("stickers.index"))


CACHE_DIR = STATE_DIR / "sticker-cache"


def _cached(sticker_id: str):
    key = hashlib.sha1(sticker_id.encode("utf-8")).hexdigest()[:20]
    data_file = CACHE_DIR / f"{key}.bin"
    meta_file = CACHE_DIR / f"{key}.ctype"
    if data_file.exists() and meta_file.exists():
        return data_file.read_bytes(), meta_file.read_text(encoding="utf-8").strip() or "image/gif"
    return None, None


@bp.get("/stickers/image/<path:sticker_id>")
@login_required
def image(sticker_id: str):
    data, ctype = _cached(sticker_id)
    if data is None:
        try:
            data, ctype = control.sticker_image(sticker_id)
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            key = hashlib.sha1(sticker_id.encode("utf-8")).hexdigest()[:20]
            (CACHE_DIR / f"{key}.bin").write_bytes(data)
            (CACHE_DIR / f"{key}.ctype").write_text(ctype, encoding="utf-8")
        except Exception:
            svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="56" height="56">'
                   '<rect width="56" height="56" fill="#222"/><text x="28" y="32" fill="#888" '
                   'font-size="10" text-anchor="middle">no image</text></svg>')
            return send_file(io.BytesIO(svg.encode("utf-8")), mimetype="image/svg+xml", max_age=30)
    return send_file(io.BytesIO(data), mimetype=ctype or "image/gif", max_age=86400)


@bp.post("/stickers/favorite")
@login_required
def favorite():
    sticker_id = (request.form.get("id") or "").strip()
    favorite = (request.form.get("favorite") or "") == "1"
    try:
        control.sticker_favorite(sticker_id, favorite)
        flash(('已标记常用' if favorite else '已取消常用') + '：' + sticker_id[-12:], "ok")
    except control.BridgeError as exc:
        flash(f"操作失败：{exc}", "error")
    return redirect(url_for("stickers.index", q=request.form.get("q") or ""))
