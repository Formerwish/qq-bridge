import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import app
from login_helper import login

app.config.update(TESTING=True)
c = app.test_client()
login(c, "admin", "Formerwish$0317")

page = c.get("/stickers")
body = page.get_data(as_text=True)
print("stickers:", page.status_code, "| 按钮:", "设为常用" in body, "| 只看常用:", "只看常用" in body)
sid = re.search(r'name="id" value="([^"]+)"', body).group(1)
csrf = re.search(r'name="csrf" content="([^"]+)"', body).group(1)

r = c.post("/stickers/favorite", data={"csrf": csrf, "id": sid, "favorite": "1", "q": ""}, follow_redirects=True)
after = r.get_data(as_text=True)
print("标记后:", "★ 常用" in after)
fav_page = c.get("/stickers?fav=1").get_data(as_text=True)
print("只看常用包含该 id:", sid[-12:] in fav_page)

# 还原
c.post("/stickers/favorite", data={"csrf": csrf, "id": sid, "favorite": "0", "q": ""}, follow_redirects=True)
print("已还原")
