import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import app
from db import execute, query
from login_helper import login
from passwords import make_password

ctx = app.app_context()
ctx.push()

USERNAME = "editor_probe"
PASSWORD = "ProbePass123"

execute("DELETE FROM kb_user WHERE username = %s", (USERNAME,))
execute(
    "INSERT INTO kb_user (username, password_hash, role, enabled) VALUES (%s, %s, 'editor', 1)",
    (USERNAME, make_password(PASSWORD)),
)

try:
    app.config.update(TESTING=True)
    c = app.test_client()
    r = login(c, USERNAME, PASSWORD)
    print("login:", r.status_code)
    for path in ["/", "/kb", "/slang"]:
        resp = c.get(path)
        print(f"{path}: {resp.status_code}")
    for path in ["/sessions", "/periods", "/tools", "/users", "/settings"]:
        resp = c.get(path)
        print(f"{path}: {resp.status_code} -> {resp.headers.get('Location', '')}")
    body = c.get("/").get_data(as_text=True)
    print("editor 菜单含会话:", "会话" in body, "| 含设置:", "设置" in body, "| 含知识库:", "知识库" in body)
    r = c.get("/kb")
    print("KB 可打开:", r.status_code == 200)
finally:
    execute("DELETE FROM kb_user WHERE username = %s", (USERNAME,))
    print("cleanup:", query("SELECT COUNT(*) AS n FROM kb_user WHERE username = %s", (USERNAME,), one=True))
    ctx.pop()
