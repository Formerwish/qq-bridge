"""测试用登录：先取 /login 触发 session，再取 /captcha 拿验证码文本，然后提交。"""

from __future__ import annotations


def fetch_captcha(client) -> str:
    client.get("/login")
    client.get("/captcha")
    with client.session_transaction() as sess:
        return sess.get("captcha", "")


def login(client, username: str, password: str):
    code = fetch_captcha(client)
    return client.post("/login", data={"username": username, "password": password, "captcha": code})
