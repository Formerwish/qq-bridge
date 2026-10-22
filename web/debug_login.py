import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import app
from login_helper import login

app.config.update(TESTING=True)
c = app.test_client()
r = login(c, "admin", "uyodBgNmq1poK1")
print("status", r.status_code)
m = re.search(r'class="error">([^<]*)', r.get_data(as_text=True))
print("error:", m.group(1) if m else None)
