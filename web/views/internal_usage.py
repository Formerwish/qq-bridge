from __future__ import annotations

from flask import Blueprint, jsonify, request

from settings import settings
import usage

bp = Blueprint("internal_usage", __name__)


@bp.post("/internal/usage")
def internal_usage():
    if (request.headers.get("x-control-token") or "") != (settings.control_token or ""):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    body = request.get_json(silent=True) or {}
    scope = str(body.get("scope") or "24h")
    day = body.get("day") or None
    conv = str(body.get("conv") or "")
    info = usage.collect(scope, day, conv)
    payload = {k: v for k, v in info.items() if k != "buckets"}
    # 分桶（小时/天）也带上，管理员问“几点最高/哪一天最多”时才能回答。
    payload["buckets"] = [
        {"label": b["label"], "tokens": b["tokens"], "cost": round(b["cost"], 6), "peak": bool(b["peak"])}
        for b in info.get("buckets", [])
    ]
    return jsonify({"ok": True, "usage": payload, "summary": usage.summary_text(info)})
