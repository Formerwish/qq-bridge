"""端到端自测：登录 → 知识条目 CRUD → 注入预览 → 黑话库 CRUD/确认 → 修订日志 → 用户页。

用 venv 里的 Python 直接跑（不依赖第三方库）：
    .venv\\Scripts\\python.exe e2e_test.py --password <admin密码>
"""

from __future__ import annotations

import argparse
import http.cookiejar
import re
import sys
import urllib.error
import urllib.parse
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None


def build_opener():
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), NoRedirect())


def get(opener, url: str) -> tuple[int, str]:
    try:
        with opener.open(url, timeout=15) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


def post(opener, url: str, data: dict) -> tuple[int, str, str]:
    body = urllib.parse.urlencode(data, encoding="utf-8").encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded; charset=utf-8")
    try:
        with opener.open(req, timeout=15) as resp:
            return resp.status, resp.headers.get("Location", ""), resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers.get("Location", ""), exc.read().decode("utf-8", "replace")


def csrf_of(html: str) -> str:
    m = re.search(r'name="csrf" value="([^"]+)"', html)
    return m.group(1) if m else ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:3210")
    ap.add_argument("--user", default="admin")
    ap.add_argument("--password", required=True)
    args = ap.parse_args()
    base = args.base.rstrip("/")

    op = build_opener()
    ok = []

    status, html = get(op, f"{base}/login")
    assert status == 200, f"GET /login => {status}"
    status, loc, body = post(op, f"{base}/login", {"csrf": csrf_of(html), "username": args.user, "password": args.password})
    assert status == 302, f"POST /login => {status}（{body[:120]}）"
    ok.append("登录")

    status, html = get(op, f"{base}/")
    assert status == 200 and "知识条目" in html, f"GET / => {status}"
    ok.append("列表")

    status, loc, _ = post(op, f"{base}/entry/new", {
        "csrf": csrf_of(html),
        "topic": "术语",
        "title": "端到端测试条目（可删）",
        "keywords": "e2e测试,待删",
        "body": "这是一条端到端测试正文：验证新增、编辑、启停、删除与修订日志。内容长度超过二十个字，用完即删。",
        "priority": "1",
        "enabled": "1",
    })
    assert status == 302, f"POST /entry/new => {status}"
    entry_id = int(re.search(r"/entry/(\d+)", loc).group(1))
    ok.append(f"新建#{entry_id}")

    status, html = get(op, f"{base}/entry/{entry_id}")
    assert status == 200 and "端到端测试条目" in html, f"GET /entry/{entry_id} => {status}"
    status, loc, _ = post(op, f"{base}/entry/{entry_id}/edit", {
        "csrf": csrf_of(html),
        "topic": "术语",
        "title": "端到端测试条目（已改）",
        "keywords": "e2e测试,待删",
        "body": "这是编辑后的正文：验证 update 与修订日志。内容同样超过二十个字，用完即删。",
        "priority": "5",
        "enabled": "1",
    })
    assert status == 302, f"POST edit => {status}"
    status, html = get(op, f"{base}/entry/{entry_id}")
    assert "（已改）" in html, "编辑后标题没变"
    ok.append("编辑")

    status, loc, _ = post(op, f"{base}/entry/{entry_id}/toggle", {"csrf": csrf_of(html)})
    assert status == 302, f"POST toggle => {status}"
    status, html = get(op, f"{base}/entry/{entry_id}")
    assert "禁用" in html, "启停后状态没变"
    ok.append("启停")

    status, html2 = get(op, f"{base}/match")
    assert status == 200 and "注入预览" in html2, f"GET /match => {status}"
    status, _loc, body = post(op, f"{base}/match", {"csrf": csrf_of(html2), "text": "这皮肤是机械师吗？BLK.TRACY 跟初音谁像"})
    assert status == 200 and "【第五人格资料】" in body, "注入预览没有生成资料块"
    ok.append("注入预览")

    status, loc, _ = post(op, f"{base}/entry/{entry_id}/delete", {"csrf": csrf_of(html)})
    assert status == 302, f"POST delete => {status}"
    status, _h = get(op, f"{base}/entry/{entry_id}")
    assert status == 404, f"删除后仍能访问：{status}"
    ok.append("删除")

    status, html = get(op, f"{base}/revisions")
    assert status == 200, f"GET /revisions => {status}"
    for action in ("create", "update", "disable", "delete"):
        assert action in html, f"修订日志缺少 {action}"
    ok.append("修订日志")

    status, html = get(op, f"{base}/users")
    assert status == 200 and "新增用户" in html, f"GET /users => {status}"
    ok.append("用户页")

    # ── 黑话库 ────────────────────────────────────────────────────────────
    status, html = get(op, f"{base}/slang")
    assert status == 200 and "黑话库" in html, f"GET /slang => {status}"
    ok.append("黑话列表")

    status, loc, _ = post(op, f"{base}/slang/new", {
        "csrf": csrf_of(html),
        "content": "e2e黑话词",
        "meaning": "端到端测试的含义",
        "usage": "测试用",
        "example": "这是 e2e 黑话词",
        "status": "candidate",
    })
    assert status == 302, f"POST /slang/new => {status}"
    slang_id = loc.rstrip("/").split("/")[-2]  # /slang/<id>/edit
    ok.append(f"黑话新增#{slang_id}")

    status, html = get(op, f"{base}/slang/{slang_id}/edit")
    assert status == 200 and "e2e黑话词" in html, f"GET slang edit => {status}"
    status, loc, _ = post(op, f"{base}/slang/{slang_id}/status", {
        "csrf": csrf_of(html), "action": "confirm", "meaning": "端到端测试的含义（已确认）",
    })
    assert status == 302, f"POST slang confirm => {status}"
    status, html = get(op, f"{base}/slang/{slang_id}/edit")
    assert "已确认" in html, "确认后状态没变"
    ok.append("黑话确认")

    status, loc, _ = post(op, f"{base}/slang/{slang_id}/delete", {"csrf": csrf_of(html)})
    assert status == 302, f"POST slang delete => {status}"
    status, _h = get(op, f"{base}/slang/{slang_id}/edit")
    assert status == 404, f"删除后仍能访问黑话：{status}"
    ok.append("黑话删除")

    print("E2E 通过：" + " / ".join(ok))
    return 0


if __name__ == "__main__":
    sys.exit(main())
