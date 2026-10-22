import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from login_helper import login as do_login

from app import app
from db import execute

app.config.update(TESTING=True)


def db(sql, params=()):
    with app.app_context():
        return execute(sql, params)


client = app.test_client()
r = do_login(client, "admin", "uyodBgNmq1poK1")
print("admin plaintext login:", r.status_code, "->", r.headers.get("Location"))

db("DELETE FROM kb_user WHERE username='hash_test'")
db("INSERT INTO kb_user (username, password_hash, role, enabled, created_by) VALUES ('hash_test', 'pbkdf2:sha256:600000$abc$def', 'editor', 1, 'selftest')")
c2 = app.test_client()
r2 = do_login(c2, "hash_test", "whatever")
body = r2.get_data(as_text=True)
print("legacy hash login:", r2.status_code)
print("提示文本 =", "用户名或密码错误" if "用户名或密码错误" in body else "其它")
print("仍含旧哈希字样:", "旧哈希" in body)
db("DELETE FROM kb_user WHERE username='hash_test'")
print("cleaned")
