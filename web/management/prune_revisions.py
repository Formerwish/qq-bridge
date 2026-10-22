"""清理修订日志（kb_revision / kb_slang_revision）。

两个表都是**纯审计日志**：AI 不读、桥接不读，删掉不影响功能。
常见需要清理的两类：

1. 无主记录 —— 目标条目/黑话已经被删了，日志还留着（e2e 测试、误建误删都会产生）；
2. 过期记录 —— 超过 N 天的历史（可选，默认不动）。

用法：
    python prune_revisions.py --dry-run     # 先看会删多少
    python prune_revisions.py               # 只删无主记录
    python prune_revisions.py --days 90     # 再删掉 90 天前的（含无主的）
"""

from __future__ import annotations

import argparse

from db import execute, query


def count_orphans() -> tuple[int, int]:
    kb = query(
        "SELECT COUNT(*) AS n FROM kb_revision r "
        "LEFT JOIN kb_entry e ON e.id = r.entry_id WHERE e.id IS NULL",
        one=True,
    )["n"]
    slang = query(
        "SELECT COUNT(*) AS n FROM kb_slang_revision r "
        "LEFT JOIN kb_slang s ON s.id = r.slang_id WHERE s.id IS NULL",
        one=True,
    )["n"]
    return int(kb), int(slang)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=0, help="一并删除 N 天前的记录（0 = 只删无主）")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    total_kb = int(query("SELECT COUNT(*) AS n FROM kb_revision", one=True)["n"])
    total_slang = int(query("SELECT COUNT(*) AS n FROM kb_slang_revision", one=True)["n"])
    orphan_kb, orphan_slang = count_orphans()
    print(f"当前：kb_revision {total_kb} 条（无主 {orphan_kb}）；kb_slang_revision {total_slang} 条（无主 {orphan_slang}）")

    if args.dry_run:
        print("[dry-run] 将删除上面列出的无主记录" + (f"，以及 {args.days} 天前的记录" if args.days else ""))
        return

    deleted_kb = execute(
        "DELETE r FROM kb_revision r LEFT JOIN kb_entry e ON e.id = r.entry_id WHERE e.id IS NULL"
    )
    deleted_slang = execute(
        "DELETE r FROM kb_slang_revision r LEFT JOIN kb_slang s ON s.id = r.slang_id WHERE s.id IS NULL"
    )
    print(f"无主记录：kb_revision -{deleted_kb}，kb_slang_revision -{deleted_slang}")

    if args.days > 0:
        old_kb = execute("DELETE FROM kb_revision WHERE created_at < NOW() - INTERVAL %s DAY", (args.days,))
        old_slang = execute("DELETE FROM kb_slang_revision WHERE created_at < NOW() - INTERVAL %s DAY", (args.days,))
        print(f"{args.days} 天前：kb_revision -{old_kb}，kb_slang_revision -{old_slang}")

    left_kb = int(query("SELECT COUNT(*) AS n FROM kb_revision", one=True)["n"])
    left_slang = int(query("SELECT COUNT(*) AS n FROM kb_slang_revision", one=True)["n"])
    print(f"剩余：kb_revision {left_kb} 条；kb_slang_revision {left_slang} 条")


if __name__ == "__main__":
    main()
