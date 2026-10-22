import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import app
from login_helper import login

app.config.update(TESTING=True)
c = app.test_client()
login(c, "admin", "Formerwish$0317")

page = c.get("/settings")
body = page.get_data(as_text=True)
print("GET", page.status_code, "| 白名单:", "白名单" in body, "| ownerQQ:", "ownerQQ" in body)
csrf = re.search(r'name="csrf" content="([^"]+)"', body).group(1)
form = {
    "csrf": csrf,
    "allow_groups": "980797902, 1039085100, 2157035230",
    "allow_private": "583937437",
    "deny_groups": "",
    "deny_private": "",
    "owner_qq": "583937437",
    "session_hours": "8",
}
r = c.post("/settings", data=form)
print("POST", r.status_code, "->", r.headers.get("Location"))
after = c.get("/settings").get_data(as_text=True)
print("保存后包含提示:", "设置已保存" in after, "| 白名单:", "白名单" in after)
