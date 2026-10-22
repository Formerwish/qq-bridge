"""用量统计：读 state/token-usage.jsonl，按范围聚合、按峰谷着色并估价。

支持范围：
- 24h  最近 24 小时（按小时）
- 7d   最近 7 天（按天）
- all  全部（按天，最多展示 180 天）
- day  指定某一天（按小时），可再叠加 conv 过滤

价格优先级：当前时段的 priceCacheHit/priceCacheMiss/priceOutput > config.pricing.models > 官方价。
"""

from __future__ import annotations

import json
import tomllib
from datetime import date, datetime, timedelta
from pathlib import Path

from settings import STATE_DIR

ROOT = Path(__file__).resolve().parents[1]
# DeepSeek 官方价（人民币元 / 百万 token，中文定价页 2026-10）
OFFICIAL_PRICE = {
    "deepseek-flash": {
        "off": {"cacheHit": 0.02, "cacheMiss": 1.0, "output": 4.0},
        "peak": {"cacheHit": 0.04, "cacheMiss": 2.0, "output": 8.0},
    },
}
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
MAX_DAYS = 180


def _load_config() -> dict:
    try:
        with (ROOT / "config.toml").open("rb") as fh:
            return tomllib.load(fh)
    except Exception:
        return {}


def _price_for(config: dict, model: str, peak: bool, period: dict | None = None) -> dict:
    official = OFFICIAL_PRICE.get("deepseek-flash", {})
    base = dict(official.get("peak" if peak else "off") or {})
    if period:
        base = {
            "cacheHit": float(period.get("priceCacheHit") or 0),
            "cacheMiss": float(period.get("priceCacheMiss") or 0),
            "output": float(period.get("priceOutput") or 0),
        }
    models = ((config.get("pricing") or {}).get("models") or {})
    entry = models.get(model) or {}
    table = entry.get("on" if peak else "off") or {}
    for k in base:
        if isinstance(table.get(k), (int, float)):
            base[k] = float(table[k])
    return base


def _in_period(period: dict, moment: datetime) -> bool:
    start = str(period.get("start") or "")
    end = str(period.get("end") or "")
    try:
        sh, sm = (int(x) for x in start.split(":"))
        eh, em = (int(x) for x in end.split(":"))
    except ValueError:
        return False
    days = [str(d).lower() for d in (period.get("days") or [])]
    candidates = [moment]
    if sh * 60 + sm > eh * 60 + em:
        candidates.append(moment - timedelta(days=1))
    for day in candidates:
        if days and WEEKDAYS[day.weekday()] not in days:
            continue
        minutes = day.hour * 60 + day.minute
        if sh * 60 + sm <= eh * 60 + em:
            if sh * 60 + sm <= minutes < eh * 60 + em:
                return True
        elif minutes >= sh * 60 + sm or minutes < eh * 60 + em:
            return True
    return False


def _period_at(config: dict, moment: datetime):
    for period in config.get("periods") or []:
        if _in_period(period, moment):
            return period
    return None


def _iter_rows(path: Path):
    if not path.exists():
        return
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                continue
            # base 是累计快照，不是增量
            if str(row.get("k") or "") not in ("turn", "delta"):
                continue
            t = row.get("t")
            if not isinstance(t, (int, float)):
                continue
            yield row, datetime.fromtimestamp(t / 1000)


def _norm_scope(scope: str) -> str:
    return scope if scope in ("24h", "7d", "all", "day") else "24h"


def _parse_day(day: str | None) -> date:
    if day:
        try:
            return datetime.strptime(day, "%Y-%m-%d").date()
        except ValueError:
            pass
    return datetime.now().date()


def _day_label(d: date) -> str:
    return d.strftime("%m-%d")


def collect(scope: str = "24h", day: str | None = None, conv: str = "") -> dict:
    scope = _norm_scope(scope)
    config = _load_config()
    path = STATE_DIR / "token-usage.jsonl"
    now = datetime.now()

    # ── 构建桶 ────────────────────────────────────────────
    buckets: list[dict] = []
    index: dict[str, dict] = {}
    if scope == "24h":
        anchor = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=23)
        for i in range(24):
            ts = anchor + timedelta(hours=i)
            buckets.append({"ts": ts, "label": ts.strftime("%H:00"), "tokens": 0, "cost": 0.0})
            index[ts.strftime("%Y-%m-%d %H")] = buckets[-1]
        start, end = anchor, now
        title = "近 24 小时"
    elif scope == "day":
        d = _parse_day(day)
        anchor = datetime.combine(d, datetime.min.time())
        for i in range(24):
            ts = anchor + timedelta(hours=i)
            buckets.append({"ts": ts, "label": ts.strftime("%H:00"), "tokens": 0, "cost": 0.0})
            index[ts.strftime("%Y-%m-%d %H")] = buckets[-1]
        start, end = anchor, anchor + timedelta(hours=23, minutes=59, seconds=59)
        title = f"{d.strftime('%Y-%m-%d')} 当天"
    else:
        end_date = now.date()
        if scope == "7d":
            start_date = end_date - timedelta(days=6)
        else:
            # 全部：从账本最早一行开始
            earliest = None
            for _row, moment in _iter_rows(path):
                if earliest is None or moment.date() < earliest:
                    earliest = moment.date()
            start_date = earliest or end_date
            if (end_date - start_date).days + 1 > MAX_DAYS:
                start_date = end_date - timedelta(days=MAX_DAYS - 1)
        d = start_date
        while d <= end_date:
            buckets.append({"ts": datetime.combine(d, datetime.min.time()), "label": _day_label(d), "tokens": 0, "cost": 0.0})
            index[d.strftime("%Y-%m-%d")] = buckets[-1]
            d += timedelta(days=1)
        start = datetime.combine(start_date, datetime.min.time())
        end = now
        title = "最近 7 天" if scope == "7d" else "全部"

    # ── 逐行累计 ──────────────────────────────────────────
    by_conv: dict[str, dict] = {}
    peak_tokens = peak_cost = off_tokens = off_cost = 0.0
    for row, moment in _iter_rows(path):
        if moment < start or moment > end:
            continue
        key = str(row.get("key") or "未知")
        if conv and key != conv:
            continue
        bucket_key = moment.strftime("%Y-%m-%d %H") if buckets[0]["label"].count(":") else moment.strftime("%Y-%m-%d")
        bucket = index.get(bucket_key)
        if bucket is None:
            continue
        b = row.get("b") or {}
        cache_hit = float(b.get("cacheHit") or 0)
        cache_miss = float(b.get("cacheMiss") or 0) + float(b.get("cacheWrite") or 0)
        output = float(b.get("output") or 0)
        tokens = int(cache_hit + cache_miss + output)
        period = _period_at(config, moment)
        peak = bool(period and "高峰" in str(period.get("name") or ""))
        price = _price_for(config, str(row.get("model") or ""), peak, period)
        cost = (
            cache_hit / 1_000_000 * price["cacheHit"]
            + cache_miss / 1_000_000 * price["cacheMiss"]
            + output / 1_000_000 * price["output"]
        )
        bucket["tokens"] += tokens
        bucket["cost"] += cost
        if peak:
            bucket["peak_tokens"] = bucket.get("peak_tokens", 0) + tokens
            bucket["peak_cost"] = bucket.get("peak_cost", 0.0) + cost
            peak_tokens += tokens
            peak_cost += cost
        else:
            bucket["off_tokens"] = bucket.get("off_tokens", 0) + tokens
            bucket["off_cost"] = bucket.get("off_cost", 0.0) + cost
            off_tokens += tokens
            off_cost += cost
        item = by_conv.setdefault(key, {"key": key, "tokens": 0, "cost": 0.0})
        item["tokens"] += tokens
        item["cost"] += cost

    for item in buckets:
        period = _period_at(config, item["ts"])
        name = str(period.get("name") or "空闲") if period else "空闲"
        # 按天聚合时不能用桶起点时刻代表一整天：以当天高峰/空闲 token 占比决定颜色。
        pt = item.get("peak_tokens", 0)
        ot = item.get("off_tokens", 0)
        item["peak"] = pt > 0 and pt >= ot
        item["period"] = name if pt or ot else name

    peak_max = max([1] + [x["tokens"] for x in buckets])
    for item in buckets:
        item["height"] = max(2.0, round(item["tokens"] / peak_max * 100, 1)) if item["tokens"] else 2.0

    conversations = sorted(by_conv.values(), key=lambda x: x["cost"], reverse=True)
    total_tokens = int(round(peak_tokens + off_tokens))
    total_cost = peak_cost + off_cost
    peak_tokens = int(round(peak_tokens))
    off_tokens = int(round(off_tokens))
    return {
        "ok": True,
        "scope": scope,
        "title": title,
        "conv": conv,
        "day": (_parse_day(day).isoformat() if scope in ("day", "7d", "all") else ""),
        "conversations": conversations,
        "buckets": buckets,
        "total_tokens": total_tokens,
        "total_cost": total_cost,
        "peak_tokens": peak_tokens,
        "off_tokens": off_tokens,
        "peak_cost": peak_cost,
        "off_cost": off_cost,
        "has_data": bool(total_tokens),
    }


def summary_text(info: dict, limit: int = 6) -> str:
    """给管理员/工具读的中文摘要。"""
    lines = [
        f"{info.get('title') or info.get('scope')}：{int(info['total_tokens']):,} tokens · ¥{info['total_cost']:.3f}",
        f"高峰 {int(info['peak_tokens']):,} tokens / ¥{info['peak_cost']:.3f}；空闲 {int(info['off_tokens']):,} tokens / ¥{info['off_cost']:.3f}",
    ]
    buckets = info.get("buckets") or []
    if buckets and info.get("scope") in ("24h", "day"):
        top_hours = sorted(buckets, key=lambda b: b["tokens"], reverse=True)[:3]
        top_hours = [b for b in top_hours if b["tokens"]]
        if top_hours:
            lines.append("小时 Top：")
            for b in top_hours:
                lines.append(f"- {b['label']}：{int(b['tokens']):,} tokens / ¥{b['cost']:.3f}")
    elif buckets:
        top_days = sorted(buckets, key=lambda b: b["tokens"], reverse=True)[:3]
        top_days = [b for b in top_days if b["tokens"]]
        if top_days:
            lines.append("日期 Top：")
            for b in top_days:
                lines.append(f"- {b['label']}：{int(b['tokens']):,} tokens / ¥{b['cost']:.3f}")
    convs = info.get("conversations") or []
    if convs:
        lines.append("会话 Top：")
        for item in convs[:limit]:
            lines.append(f"- {item['key']}：{int(item['tokens']):,} tokens / ¥{item['cost']:.3f}")
    else:
        lines.append("该范围没有用量记录。")
    return "\n".join(lines)
