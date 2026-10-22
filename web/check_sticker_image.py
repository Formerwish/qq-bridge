import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import app
from login_helper import login

app.config.update(TESTING=True)
c = app.test_client()
login(c, "admin", "Formerwish$0317")

state = json.loads(Path(r"E:\qq-bridge\state\stickers.json").read_text(encoding="utf-8"))
sticker = state[0]
sid = sticker["id"]
r = c.get("/stickers/image/" + sid)
print("image status:", r.status_code, "content-type:", r.headers.get("Content-Type"), "bytes:", len(r.data))
cache = Path(r"E:\qq-bridge\state\sticker-cache")
print("cache files:", len(list(cache.glob('*.bin'))) if cache.exists() else 0)
page = c.get("/stickers").get_data(as_text=True)
print("页面含 img:", '/stickers/image/' in page, "| 缩略图 class:", 'sticker-thumb' in page)
