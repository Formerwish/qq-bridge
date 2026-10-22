"""知识库/黑话写路径冒烟测试（真 DB，创建后自动清理）。

cd web && .venv\\Scripts\\python selftest_kb.py
需要 MySQL 在跑；账号密码通过 QQ_SELFTEST_PASSWORD 提供。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from login_helper import login as do_login

from app import app  # noqa: E402
from db import execute, query  # noqa: E402


def q(sql, params=(), one=False):
    with app.app_context():
        return query(sql, params, one=one)


def ex(sql, params=()):
    with app.app_context():
        return execute(sql, params)

USERNAME = os.environ.get("QQ_SELFTEST_USER", "admin")
PASSWORD = os.environ.get("QQ_SELFTEST_PASSWORD", "")

passed = 0
failed = 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✓ {name}")
    else:
        failed += 1
        print(f"  ✗ {name} {detail}")


def main() -> int:
    if not PASSWORD:
        print("需要 QQ_SELFTEST_PASSWORD")
        return 1
    app.config.update(TESTING=True)
    client = app.test_client()
    assert do_login(client, USERNAME, PASSWORD).status_code == 302
    home = client.get("/").get_data(as_text=True)
    import re
    csrf = re.search(r'name="csrf" content="([^"]+)"', home).group(1)
    form = {"csrf": csrf, "topic": "自检", "title": "[selftest] 临时条目", "keywords": "自检关键词,selftestkw",
            "body": "这条是自检写入的临时内容，测试结束会删除。", "priority": "1", "enabled": "on"}

    entry_id = None
    slang_id = "selftest-slang-0001"
    try:
        r = client.post("/kb/new", data=form)
        check("新建条目 302", r.status_code == 302)
        row = q("SELECT * FROM kb_entry WHERE title = %s ORDER BY id DESC", ("[selftest] 临时条目",), one=True)
        entry_id = row["id"] if row else None
        check("条目已入库", bool(entry_id) and row["keywords"] == form["keywords"])

        r = client.post(f"/kb/{entry_id}/edit", data={**form, "title": "[selftest] 已改名"})
        check("编辑条目 302", r.status_code == 302)
        updated = q("SELECT title FROM kb_entry WHERE id = %s", (entry_id,), one=True)
        check("编辑已生效", updated and updated["title"] == "[selftest] 已改名")

        r = client.post("/kb/preview", data={"csrf": csrf, "text": "随便说说自检关键词怎么样"})
        body = r.get_data(as_text=True)
        check("注入预览命中新条目", r.status_code == 200 and "已改名" in body and "第五人格资料" in body)

        r = client.get("/revisions")
        check("修订记录出现", r.status_code == 200 and "[selftest]" in r.get_data(as_text=True))

        r = client.post(f"/kb/{entry_id}/delete", data={"csrf": csrf})
        check("删除条目 302", r.status_code == 302)
        check("条目已删除", q("SELECT id FROM kb_entry WHERE id = %s", (entry_id,), one=True) is None)
        entry_id = None

        # 黑话：插入一条临时候选，走状态流转再删除（通过 SQL 造数据，页面验证列表渲染与状态接口）
        ex(
            "INSERT INTO kb_slang (id, content, meaning, `usage`, example, risk, status, source, `count`, updated_ms) "
            "VALUES (%s, %s, %s, %s, %s, %s, 'candidate', 'ai', 0, %s)",
            (slang_id, "[自检]测试词", "测试含义", "测试用法", "测试示例", "", 1),
        )
        r = client.get("/slang?status=candidate")
        check("黑话候选页出现临时词", r.status_code == 200 and "[自检]测试词" in r.get_data(as_text=True))
        r = client.post(f"/slang/{slang_id}/status", data={"csrf": csrf, "status": "confirmed"})
        check("黑话确认 302", r.status_code == 302)
        row = q("SELECT status FROM kb_slang WHERE id = %s", (slang_id,), one=True)
        check("黑话状态已更新", row and row["status"] == "confirmed")
        r = client.post(f"/slang/{slang_id}/delete", data={"csrf": csrf})
        check("黑话删除 302", r.status_code == 302)
        check("黑话已删除", q("SELECT id FROM kb_slang WHERE id = %s", (slang_id,), one=True) is None)
    finally:
        if entry_id:
            ex("DELETE FROM kb_entry WHERE id = %s", (entry_id,))

    print(f"\n通过 {passed} 项，失败 {failed} 项。")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
