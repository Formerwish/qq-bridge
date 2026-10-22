"""高级配置：全量 config.toml，汉化标签 + 选项控件；与专用页面不重复。"""

from __future__ import annotations

import control
from flask import Blueprint, flash, redirect, render_template, request, url_for

from config_schema import GROUP_ORDER, build_fields, duration_factor, group_key, group_label, kind_for
from views.auth import login_required

bp = Blueprint("config", __name__)


@bp.get("/config")
@login_required
def index():
    error = None
    fields = []
    meta = {}
    try:
        info = control.config_full()
        meta = {k["path"]: k for k in info.get("keys") or []}
        fields = build_fields(info.get("config") or {})
    except control.BridgeError as exc:
        error = str(exc)
    groups: dict[str, list] = {}
    for f in fields:
        key = group_key(f["path"])
        f["hot"] = bool(meta.get(f["path"], {}).get("hot"))
        f["restart"] = bool(meta.get(f["path"], {}).get("restart")) or not f["hot"]
        groups.setdefault(key, []).append(f)
    order_index = {k: i for i, k in enumerate(GROUP_ORDER)}
    keys = sorted(groups, key=lambda k: (order_index.get(k, len(GROUP_ORDER)), k))
    ordered = [
        {
            "key": k,
            "label": group_label(k),
            "fields": groups[k],
            "restart_count": sum(1 for f in groups[k] if f["restart"]),
        }
        for k in keys
    ]
    return render_template("config.html", groups=ordered, error=error, total=len(fields))


@bp.post("/config")
@login_required
def save():
    updates = {}
    try:
        for key, raw in request.form.items():
            if not key.startswith("f."):
                continue
            path = key[2:]
            kind = kind_for(path)
            if kind == "auto":
                kind = request.form.get("kind." + path, "text")
            if kind == "bool":
                updates[path] = raw == "on"
            elif kind == "duration":
                raw = raw.strip()
                if not raw:
                    continue
                unit = request.form.get("unit." + path, "秒")
                factor = duration_factor(unit)
                updates[path] = int(round(float(raw) * factor))
            elif kind == "percent":
                raw = raw.strip().rstrip("%").strip()
                if not raw:
                    continue
                pct = float(raw)
                if pct < 0 or pct > 100:
                    raise ValueError(f"概率必须在 0~100 之间：{path}")
                updates[path] = pct / 100
            elif kind == "number":
                raw = raw.strip()
                if not raw:
                    continue
                updates[path] = float(raw) if ("." in raw or "e" in raw.lower()) else int(raw)
            elif kind == "list":
                updates[path] = [x.strip() for x in raw.replace("\n", ",").split(",") if x.strip()]
            else:
                updates[path] = raw
    except ValueError as exc:
        flash(f"保存失败：{exc}", "error")
        return redirect(url_for("config.index"))
    if not updates:
        flash("没有需要保存的修改", "error")
        return redirect(url_for("config.index"))
    try:
        result = control.config_save(updates)
        msg = f"已热更 {len(result.get('applied') or [])} 项"
        if result.get("requiresRestart"):
            msg += "；需重启桥接：" + ", ".join(result["requiresRestart"])
        flash(msg, "ok")
    except control.BridgeError as exc:
        flash(f"保存失败：{exc}", "error")
    return redirect(url_for("config.index"))
