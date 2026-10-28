"""峰谷策略页：编辑 `[[periods]]`（任意多段），保存后写 config.toml 并让桥接热重载。

字段：名称 / 开始 / 结束（支持跨零点）/ 星期（可空=每天）/ 回复概率(%) /
推理强度 / 模型 / 主动检查开关 / 全部聊天合计的每分钟·每小时发送上限 / 分群限额（groupLimits）。
空着的字段不写入 → 该时段不覆盖对应全局默认值。
"""

from __future__ import annotations

import config_edit
import control
from flask import Blueprint, flash, redirect, render_template, request, url_for

from views.auth import login_required

bp = Blueprint("periods", __name__)

EFFORTS = ["", "low", "high", "max"]


def _rows_from_config() -> list[dict]:
    try:
        data = config_edit.load()
    except config_edit.ConfigEditError:
        return []
    rows = []
    for item in data.get("periods") or []:
        if not isinstance(item, dict):
            continue
        rows.append({
            "name": item.get("name", ""),
            "start": item.get("start", ""),
            "end": item.get("end", ""),
            "days": ",".join(item.get("days") or []),
            "probability": "" if item.get("replyProbability") is None else f"{float(item['replyProbability']) * 100:g}",
            "effort": item.get("reasoningEffort") or "",
            "model": item.get("model") or "",
            "proactive": item.get("proactive"),
            "slangAutoLearn": item.get("slangAutoLearn"),
            "priceCacheHit": item.get("priceCacheHit", ""),
        "priceCacheMiss": item.get("priceCacheMiss", ""),
        "priceOutput": item.get("priceOutput", ""),
        "perMinute": int(item["sendMaxPerMinute"]) if item.get("sendMaxPerMinute") not in (None, "") else "",
            "perHour": int(item["sendMaxPerHour"]) if item.get("sendMaxPerHour") not in (None, "") else "",
            "groupLimits": [
                {
                    "groups": ",".join(str(g) for g in (gl.get("groups") or [])),
                    "perMinute": gl.get("perMinute") or "",
                    "perHour": gl.get("perHour") or "",
                }
                for gl in (item.get("groupLimits") or []) if isinstance(gl, dict)
            ],
        })
    return rows


@bp.get("/periods")
@login_required
def index():
    error = None
    info = None
    try:
        info = control.periods()
    except control.BridgeError as exc:
        error = str(exc)
    return render_template("periods.html", rows=_rows_from_config(), efforts=EFFORTS, info=info, error=error)


def _parse_group_spec(spec: str) -> list[dict]:
    """``群号,群号:每分钟:每小时;群号:每分钟:每小时`` → 结构化列表。"""
    out = []
    for chunk in (spec or "").split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts = [x.strip() for x in chunk.split(":")]
        if len(parts) < 2:
            continue
        groups = [g for g in parts[0].replace("，", ",").split(",") if g.strip().isdigit()]
        if not groups:
            continue
        per_minute = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
        per_hour = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None
        if per_minute is None and per_hour is None:
            continue
        out.append({"groups": groups, "perMinute": per_minute, "perHour": per_hour})
    return out


def _num(value, scale=1.0):
    text = (value or "").strip()
    if not text:
        return None
    try:
        return float(text) / scale
    except ValueError:
        return None


@bp.post("/periods")
@login_required
def save():
    names = request.form.getlist("name")
    starts = request.form.getlist("start")
    ends = request.form.getlist("end")
    days = request.form.getlist("days")
    probs = request.form.getlist("probability")
    efforts = request.form.getlist("effort")
    models = request.form.getlist("model")
    prices_hit = request.form.getlist("priceCacheHit")
    prices_miss = request.form.getlist("priceCacheMiss")
    prices_out = request.form.getlist("priceOutput")
    per_minutes = request.form.getlist("perMinute")
    per_hours = request.form.getlist("perHour")
    proactives = request.form.getlist("proactive")  # 不覆盖 / on / off
    slang_learns = request.form.getlist("slangAutoLearn")  # 不覆盖 / on / off
    group_specs = request.form.getlist("glSpec")

    periods = []
    for idx, name in enumerate(names):
        start = (starts[idx] if idx < len(starts) else "").strip()
        end = (ends[idx] if idx < len(ends) else "").strip()
        if not start or not end:
            continue
        probability = _num(probs[idx] if idx < len(probs) else "", 100.0)
        period = {
            "name": (name or "").strip() or f"时段{len(periods) + 1}",
            "start": start,
            "end": end,
            "days": [d.strip() for d in (days[idx] if idx < len(days) else "").replace("，", ",").split(",") if d.strip()] or None,
            "replyProbability": None if not probability else max(0.0, min(1.0, probability)),
            "reasoningEffort": (efforts[idx] if idx < len(efforts) else "").strip() or None,
            "model": (models[idx] if idx < len(models) else "").strip() or None,
            "proactive": {"on": True, "off": False}.get((proactives[idx] if idx < len(proactives) else "").strip()),
            "slangAutoLearn": {"on": True, "off": False}.get((slang_learns[idx] if idx < len(slang_learns) else "").strip()),
            "priceCacheHit": _num(prices_hit[idx] if idx < len(prices_hit) else ""),
        "priceCacheMiss": _num(prices_miss[idx] if idx < len(prices_miss) else ""),
        "priceOutput": _num(prices_out[idx] if idx < len(prices_out) else ""),
            "groupLimits": _parse_group_spec(group_specs[idx] if idx < len(group_specs) else ""),
        "sendMaxPerMinute": (int(v) if (v := _num(per_minutes[idx] if idx < len(per_minutes) else "")) is not None else None),
            "sendMaxPerHour": (int(v) if (v := _num(per_hours[idx] if idx < len(per_hours) else "")) is not None else None),
        }
        periods.append(period)

    try:
        config_edit.set_periods(periods)
    except config_edit.ConfigEditError as exc:
        flash(f"保存失败：{exc}", "error")
        return redirect(url_for("periods.index"))

    hint = f"已写入 {len(periods)} 个时段"
    try:
        control.reload_config()
        hint += "，桥接已热重载（下一轮唤醒生效）"
    except control.BridgeError as exc:
        hint += f"；桥接未重载（{exc}），下次启动生效"
    flash(hint, "ok")
    return redirect(url_for("periods.index"))
