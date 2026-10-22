import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import app
from login_helper import login

app.config.update(TESTING=True)
c = app.test_client()
r = login(c, "admin", "Formerwish$0317")
print("login:", r.status_code)
for path in ["/sessions", "/sessions?key=private:583937437", "/sessions?key=group:1039085100"]:
    resp = c.get(path)
    body = resp.get_data(as_text=True)
    print(path, "->", resp.status_code,
          "| 私聊模式:", "私聊模式" in body,
          "| 唤醒配置:", "保存唤醒配置" in body,
          "| 未读清空:", "未读清空" in body)
