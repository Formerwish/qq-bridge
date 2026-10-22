"""把桥接现有的 state/slang.json 导入 kb_slang（幂等）。

为什么需要单独一个脚本：
- 桥接启动时也会自动导入（库为空 + 本地有数据），但那要等它下一次重启；
- 这里可以立刻导，并且**按 updated_ms 取大值**，不会把后台里更新的条目覆盖回旧版。

用法：
    python import_slang.py                     # 从 config.json 的 bridge.slangJson 读
    python import_slang.py --file D:\\path\\slang.json
    python import_slang.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone

from db import execute, load_config, query

CFG = load_config()
DEFAULT_JSON = (CFG.get("bridge") or {}).get("slangJson") or r"E:\qq-bridge-0.2.0-r4\state\slang.json"


def ms_of(value: str | None) -> int:
    if not value:
        return 0
    try:
        text = str(value).replace("Z", "+00:00")
        return int(datetime.fromisoformat(text).astimezone(timezone.utc).timestamp() * 1000)
    except Exception:
        return 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=DEFAULT_JSON)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(args.file):
        raise SystemExit(f"找不到黑话文件：{args.file}")

    with open(args.file, "r", encoding="utf-8") as fh:
        entries = json.load(fh)
    if not isinstance(entries, list):
        raise SystemExit("slang.json 顶层不是数组，拒绝导入")

    print(f"来源：{args.file}（{len(entries)} 条）")
    inserted = updated = skipped = 0
    for entry in entries:
        content = (entry.get("content") or "").strip()
        if not content:
            continue
        sid = (entry.get("id") or "").strip() or content[:32]
        created_ms = ms_of(entry.get("createdAt")) or int(datetime.now().timestamp() * 1000)
        updated_ms = max(ms_of(entry.get("updatedAt")), created_ms)
        row = query("SELECT id, updated_ms FROM kb_slang WHERE id = %s OR content = %s", (sid, content), one=True)
        if row and int(row["updated_ms"] or 0) >= updated_ms:
            skipped += 1
            continue
        if args.dry_run:
            print(f"[dry-run] {'更新' if row else '新增'} {content}（{entry.get('status')}）")
            inserted += 0 if row else 1
            updated += 1 if row else 0
            continue
        if row:
            execute(
                "UPDATE kb_slang SET meaning=%s, `usage`=%s, example=%s, risk=%s, status=%s, source=%s, "
                "count=%s, sources_json=%s, evidence_json=%s, last_inference_count=%s, updated_ms=%s WHERE id=%s",
                (
                    entry.get("meaning") or "", entry.get("usage") or "", entry.get("example") or "",
                    entry.get("risk") or "", entry.get("status") or "candidate",
                    entry.get("source") or "ai", int(entry.get("count") or 0),
                    json.dumps(entry.get("sources") or [], ensure_ascii=False),
                    json.dumps(entry.get("evidence") or [], ensure_ascii=False),
                    int(entry.get("lastInferenceCount") or 0), updated_ms, row["id"],
                ),
            )
            updated += 1
        else:
            execute(
                "INSERT INTO kb_slang (id, content, meaning, `usage`, example, risk, status, source, count, "
                "sources_json, evidence_json, last_inference_count, created_ms, updated_ms) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    sid, content, entry.get("meaning") or "", entry.get("usage") or "", entry.get("example") or "",
                    entry.get("risk") or "", entry.get("status") or "candidate", entry.get("source") or "ai",
                    int(entry.get("count") or 0),
                    json.dumps(entry.get("sources") or [], ensure_ascii=False),
                    json.dumps(entry.get("evidence") or [], ensure_ascii=False),
                    int(entry.get("lastInferenceCount") or 0), created_ms, updated_ms,
                ),
            )
            inserted += 1

    print(f"完成：新增 {inserted} 条，更新 {updated} 条，跳过 {skipped} 条（库里更新）。")


if __name__ == "__main__":
    main()
