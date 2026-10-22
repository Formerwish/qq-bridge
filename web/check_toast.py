import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import app
from login_helper import login

app.config.update(TESTING=True)
c = app.test_client()
login(c, "admin", "Formerwish$0317")
page = c.get("/sessions").get_data(as_text=True)
csrf = re.search(r'name="csrf" content="([^"]+)"', page).group(1)
r = c.post("/sessions/group:999999/reset", data={"csrf": csrf}, follow_redirects=True)
body = r.get_data(as_text=True)
print("status:", r.status_code)
print("toast 容器:", 'id="toast-stack"' in body)
print("flash 提示:", "重置失败" in body)
