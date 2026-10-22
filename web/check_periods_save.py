import re
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import app
from login_helper import login

cfg_path = Path(r"E:\qq-bridge\config.toml")
app.config.update(TESTING=True)
c = app.test_client()
login(c, "admin", "Formerwish$0317")
page = c.get("/periods").get_data(as_text=True)
csrf = re.search(r'name="csrf" content="([^"]+)"', page).group(1)
print("三态 select:", 'name="proactive"' in page, "| on 选中:", 'value="on" selected' in page)

form = [
    ("csrf", csrf),
    ("name", "高峰-上午"), ("start", "09:00"), ("end", "12:00"), ("days", "mon,tue,wed,thu,fri"),
    ("probability", "15"), ("effort", "medium"), ("model", ""), ("proactive", "off"), ("perMinute", ""), ("perHour", "100"),
    ("name", "高峰-下午"), ("start", "14:00"), ("end", "18:00"), ("days", "mon,tue,wed,thu,fri"),
    ("probability", "15"), ("effort", "medium"), ("model", ""), ("proactive", "off"), ("perMinute", ""), ("perHour", "100"),
    ("name", "空闲-夜间"), ("start", "18:00"), ("end", "09:00"), ("days", ""),
    ("probability", "30"), ("effort", "high"), ("model", ""), ("proactive", "on"), ("perMinute", ""), ("perHour", "600"),
    ("name", "空闲-白天"), ("start", "09:00"), ("end", "18:00"), ("days", ""),
    ("probability", "30"), ("effort", "high"), ("model", ""), ("proactive", "on"), ("perMinute", ""), ("perHour", "600"),
]
from collections import defaultdict
bag = defaultdict(list)
for k, v in form:
    bag[k].append(v)
r = c.post("/periods", data=dict(bag), follow_redirects=False)
print("保存:", r.status_code, "->", r.headers.get("Location"))
data = tomllib.loads(cfg_path.read_text(encoding="utf-8"))
for p in data["periods"]:
    print(" ", p["name"], "proactive=", p.get("proactive"))
after = c.get("/periods").get_data(as_text=True)
print("保存后页面: on 选中", 'value="on" selected' in after, "| off 选中", 'value="off" selected' in after)
