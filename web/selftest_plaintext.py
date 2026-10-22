import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from login_helper import login as do_login

from app import app
from db import execute, query

app.config.update(TESTING=True)


def db(sql, params=(), one=False):
    with app.app_context():
        if sql.strip().upper().startswith(("INSERT", "UPDATE", "DELETE")):
            return execute(sql, params)
        return query(sql, params, one=one)


client = app.test_client()
r = do_login(client, "admin", "uyodBgNmq1poK1")
print("hash admin login:", r.status_code, "->", r.headers.get("Location"))

db("DELETE FROM kb_user WHERE username = %s", ("pt_test_user",))
db("INSERT INTO kb_user (username, password_hash, role, enabled, created_by) VALUES (%s, %s, 'editor', 1, 'selftest')",
   ("pt_test_user", "PlainText123"))
row = db("SELECT password_hash FROM kb_user WHERE username = %s", ("pt_test_user",), one=True)
print("stored:", row["password_hash"] if row else None)

c2 = app.test_client()
r2 = do_login(c2, "pt_test_user", "PlainText123")
print("plaintext login:", r2.status_code, "->", r2.headers.get("Location"))

c3 = app.test_client()
r3 = do_login(c3, "pt_test_user", "wrong")
print("wrong password:", r3.status_code)

db("DELETE FROM kb_user WHERE username = %s", ("pt_test_user",))
print("cleaned:", db("SELECT id FROM kb_user WHERE username = %s", ("pt_test_user",), one=True))
