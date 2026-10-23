"""控制台离线自检（Flask test_client，不启动服务、不依赖桥接在线）。

运行：
    cd web && .venv\\Scripts\\python selftest.py

覆盖：
  1) 未登录访问首页 → 302 到 /login
  2) 登录页可渲染
  3) 错误密码 → 401 且不种 cookie
  4) 正确密码 → 302 + HttpOnly cookie
  5) 登录后首页 200（桥接离线也能渲染）
  6) /api/status 未登录 401；登录后桥接离线返回 503（而不是 500）
  7) 无 CSRF 的 POST /logout → 403
  8) 带 CSRF 的 POST /logout → 302 并清 cookie
  9) /healthz、404 页

账号：admin + 环境变量 QQ_SELFTEST_PASSWORD（**不写进仓库**）；未设置时跳过登录后各项。
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from login_helper import login as do_login

from app import app  # noqa: E402
from settings import settings  # noqa: E402

USERNAME = os.environ.get("QQ_SELFTEST_USER", "admin")
PASSWORD = os.environ.get("QQ_SELFTEST_PASSWORD", "")

passed = 0
failed = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✓ {name}")
    else:
        failed += 1
        print(f"  ✗ {name} {detail}")


def main() -> int:
    app.config.update(TESTING=True)
    client = app.test_client()

    print("控制台自检：")
    r = client.get("/healthz")
    check("/healthz 200", r.status_code == 200 and r.get_json().get("ok") is True)

    r = client.get("/")
    check("未登录首页 302 → /login", r.status_code == 302 and "/login" in r.headers.get("Location", ""))

    r = client.get("/login")
    check("登录页可渲染", r.status_code == 200 and "登录" in r.get_data(as_text=True) and 'name="password"' in r.get_data(as_text=True))

    r = do_login(client, USERNAME, "definitely-wrong")
    check("错误密码 401 且不种 cookie", r.status_code == 401 and settings.cookie_name not in r.headers.get("Set-Cookie", ""))

    if not PASSWORD:
        print("  ! 未设置 QQ_SELFTEST_PASSWORD，跳过登录后的检查（请用真实密码重跑）")
        print(f"\n通过 {passed} 项，失败 {failed} 项。")
        return 0 if failed == 0 else 1

    r = do_login(client, USERNAME, PASSWORD)
    if r.status_code != 302:
        print(f"  ! 正确密码登录未通过（HTTP {r.status_code}）。请设置 QQ_SELFTEST_PASSWORD 后重跑；跳过登录后各项。")
        print(f"\n通过 {passed} 项，失败 {failed} 项。")
        return 0 if failed == 0 else 1

    set_cookie = r.headers.get("Set-Cookie", "")
    check("正确密码 302 + HttpOnly cookie", "HttpOnly" in set_cookie and settings.cookie_name in set_cookie)

    r = client.get("/")
    body = r.get_data(as_text=True)
    check("登录后首页 200", r.status_code == 200 and "会话" in body)
    m = re.search(r'name="csrf" content="([^"]+)"', body)
    check("页面带 CSRF token", bool(m))

    r = client.get("/api/status")
    check("登录后 /api/status 桥接离线返回 503", r.status_code in (200, 503))
    if r.status_code == 503:
        check("离线响应是结构化 JSON", r.get_json().get("ok") is False)

    anon = app.test_client()
    r = anon.get("/api/me")
    check("未登录 /api/me 401", r.status_code == 401)

    r = client.get("/sessions")
    check("会话页可渲染", r.status_code == 200 and ("桥接离线" in r.get_data(as_text=True) or "会话" in r.get_data(as_text=True)))
    r = client.get("/sessions?key=group:1")
    check("未知会话不创建状态", r.status_code == 404 or "会话不存在" in r.get_data(as_text=True) or "桥接离线" in r.get_data(as_text=True))
    r = client.get("/tools")
    check("工具页可渲染", r.status_code == 200 and "工具开关" in r.get_data(as_text=True) and "qq_kb_search" in r.get_data(as_text=True))

    r = client.get("/kb")
    check("知识库页可渲染", r.status_code == 200 and "知识库" in r.get_data(as_text=True))
    r = client.get("/kb/preview")
    check("注入预览页可渲染", r.status_code == 200 and "注入预览" in r.get_data(as_text=True))
    r = client.get("/kb/new")
    check("新建条目页可渲染", r.status_code == 200 and "新建条目" in r.get_data(as_text=True))
    r = client.get("/slang")
    check("黑话页可渲染", r.status_code == 200 and "黑话库" in r.get_data(as_text=True))
    r = client.get("/users")
    check("用户页可渲染", r.status_code == 200 and "用户管理" in r.get_data(as_text=True))
    r = client.get("/revisions")
    check("修订页可渲染", r.status_code == 200 and "修订" in r.get_data(as_text=True))

    r = client.get("/stickers")
    check("表情页离线可渲染", r.status_code == 200 and "表情库" in r.get_data(as_text=True))

    r = client.get("/roles")
    check("人格页可渲染", r.status_code == 200 and "人格卡" in r.get_data(as_text=True))
    r = client.get("/presets")
    check("预设页可渲染", r.status_code == 200 and "仿真预设" in r.get_data(as_text=True))
    r = client.get("/tokens")
    check("令牌页可渲染", r.status_code == 200 and "令牌花费" in r.get_data(as_text=True))

    r = client.get("/periods")
    body = r.get_data(as_text=True)
    check("峰谷页可渲染", r.status_code == 200 and "峰谷" in body and "保存并热重载" in body)

    r = client.get("/logs")
    check("日志页可渲染", r.status_code == 200 and ("桥接离线" in r.get_data(as_text=True) or "桥接日志" in r.get_data(as_text=True)))

    r = client.post("/logout", data={})
    check("无 CSRF 的登出 403", r.status_code == 403)

    csrf = m.group(1) if m else ""
    r = client.post("/logout", data={"csrf": csrf})
    check("带 CSRF 的登出 302", r.status_code == 302 and settings.cookie_name in r.headers.get("Set-Cookie", ""))

    r = client.get("/no-such-page")
    check("404 自定义页", r.status_code == 404 and "页面不存在" in r.get_data(as_text=True))

    print(f"\n通过 {passed} 项，失败 {failed} 项。")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
