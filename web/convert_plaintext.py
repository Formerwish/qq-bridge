import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from login_helper import login as do_login

from app import app
from db import execute, query


def db(sql, params=(), one=False):
    with app.app_context():
        if sql.strip().upper().startswith(("INSERT", "UPDATE", "DELETE")):
            return execute(sql, params)
        return query(sql, params, one=one)


# 1) admin 旧哈希 → 明文（密码不变）
row = db("SELECT password_hash FROM kb_user WHERE username='admin'", one=True)
print("before:", (row["password_hash"] or "")[:24], "...")
if row and not row["password_hash"].startswith(("pbkdf2:", "scrypt:", "argon2:")):
    print("already plaintext")
else:
    db("UPDATE kb_user SET password_hash = %s WHERE username='admin'", ("uyodBgNmq1poK1",))
print("after:", db("SELECT password_hash FROM kb_user WHERE username='admin'", one=True)["password_hash"])

# 2) 明文登录成功
c = app.test_client()
r = do_login(c, "admin", "uyodBgNmq1poK1")
print("login plaintext:", r.status_code, "->", r.headers.get("Location"))

# 3) 旧哈希行必须被拒绝（造一个临时哈希用户）
db("DELETE FROM kb_user WHERE username='hash_test'")
db("INSERT INTO kb_user (username, password_hash, role, enabled, created_by) VALUES ('hash_test', 'pbkdf2:sha256:600000$abc$def', 'editor', 1, 'selftest')")
c2 = app.test_client()
r2 = do_login(c2, "hash_test", "whatever")
print("legacy hash login:", r2.status_code, "| 提示含旧哈希:", "旧哈希" in r2.get_data(as_text=True))
db("DELETE FROM kb_user WHERE username='hash_test'")
print("cleaned:", db("SELECT id FROM kb_user WHERE username='hash_test'", one=True))
