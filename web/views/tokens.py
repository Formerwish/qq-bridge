"""令牌花费页：直接解析 state/token-usage.jsonl（桥接的账本），不依赖桥接在线。

账本每行结构：{k:"base"|"delta", t, sid, key, model, provider, b:{cacheMiss,cacheHit,cacheWrite,output,reasoning}}
这里只做展示聚合（总量 / 按天 / 按模型 / 按会话），不做计价。
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime

from flask import Blueprint, render_template

from settings import STATE_DIR
from views.auth import login_required

bp = Blueprint("tokens", __name__)

FIELDS = ["cacheMiss", "cacheHit", "cacheWrite", "output", "reasoning"]
MAX_BYTES = 64 * 1024 * 1024


def _load() -> dict:
    path = STATE_DIR / "token-usage.jsonl"
    totals = {k: 0 for k in FIELDS}
    by_model: dict[str, dict] = defaultdict(lambda: {k: 0 for k in FIELDS})
    by_day: dict[str, dict] = defaultdict(lambda: {k: 0 for k in FIELDS})
    by_key: dict[str, dict] = defaultdict(lambda: {k: 0 for k in FIELDS})
    lines = 0
    bad = 0
    last_t = None
    if not path.exists():
        return {"ok": False, "reason": "账本文件不存在", "totals": totals, "lines": 0}
    if path.stat().st_size > MAX_BYTES:
        return {"ok": False, "reason": "账本过大，已跳过解析", "totals": totals, "lines": 0}
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            lines += 1
            try:
                item = json.loads(raw)
            except json.JSONDecodeError:
                bad += 1
                continue
            bucket = item.get("b") or {}
            day = datetime.fromtimestamp((item.get("t") or 0) / 1000).strftime("%Y-%m-%d")
            model = item.get("model") or "unknown"
            key = item.get("key") or "-"
            last_t = max(last_t or 0, item.get("t") or 0)
            for field in FIELDS:
                value = int(bucket.get(field) or 0)
                totals[field] += value
                by_model[model][field] += value
                by_day[day][field] += value
                by_key[key][field] += value
    return {
        "ok": True,
        "lines": lines,
        "bad": bad,
        "totals": totals,
        "by_model": sorted(by_model.items(), key=lambda kv: -sum(kv[1].values())),
        "by_day": sorted(by_day.items(), key=lambda kv: kv[0], reverse=True)[:30],
        "by_key": sorted(by_key.items(), key=lambda kv: -sum(kv[1].values()))[:20],
        "last_t": last_t,
    }


@bp.get("/tokens")
@login_required
def index():
    return render_template("tokens.html", data=_load(), fields=FIELDS)
