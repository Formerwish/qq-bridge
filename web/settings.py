"""读取 config.toml（Python 内置 tomllib），并集中处理控制台自身的运行参数。

配置来源优先级：
  1) 环境变量 QQ_CONSOLE_*（部署/测试用）
  2) config.toml 的 [web] / [kb.mysql] 段
  3) 代码内默认值

注意：控制台**不写** config.toml（写配置属于后续阶段，会用定向改写保留注释）。
"""

from __future__ import annotations

import os
import secrets
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_TOML = REPO_ROOT / "config.toml"
CONFIG_JSON = REPO_ROOT / "config.json"
STATE_DIR = REPO_ROOT / "state"
SECRET_FILE = STATE_DIR / "web-secret"


def _load_config_file() -> dict:
    if CONFIG_TOML.exists():
        with CONFIG_TOML.open("rb") as fh:
            return tomllib.load(fh)
    if CONFIG_JSON.exists():
        import json

        return json.loads(CONFIG_JSON.read_text(encoding="utf-8"))
    return {}


RAW = _load_config_file()
WEB = RAW.get("web") or {}
MYSQL = (RAW.get("kb") or {}).get("mysql") or {}


def _env(name: str, default: str) -> str:
    return os.environ.get(f"QQ_CONSOLE_{name}", default)


def _jwt_secret() -> str:
    """JWT 密钥：环境变量 > state/web-secret（首次自动生成，gitignore）。"""
    env = os.environ.get("QQ_CONSOLE_SECRET")
    if env:
        return env
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if SECRET_FILE.exists():
        value = SECRET_FILE.read_text(encoding="utf-8").strip()
        if value:
            return value
    value = secrets.token_urlsafe(48)
    SECRET_FILE.write_text(value, encoding="utf-8")
    try:
        SECRET_FILE.chmod(0o600)
    except OSError:
        pass
    return value


class Settings:
    bind = _env("BIND", str(WEB.get("bind", "0.0.0.0")))
    port = int(_env("PORT", str(WEB.get("port", 21001))))
    bridge_url = _env("BRIDGE_URL", str(WEB.get("bridgeUrl", "http://127.0.0.1:3100"))).rstrip("/")
    # 桥接控制台令牌：只在本进程内使用，绝不下发到浏览器。
    control_token = _env("CONTROL_TOKEN", str(RAW.get("consoleToken") or ""))
    session_hours = int(_env("SESSION_HOURS", str(WEB.get("sessionHours", 8))))
    jwt_secret = _jwt_secret()
    jwt_alg = "HS256"
    cookie_name = "qq_console"
    login_rate_limit = int(_env("LOGIN_RATE", str(WEB.get("loginRate", 8))))
    login_rate_window = 300

    mysql_host = MYSQL.get("host", "127.0.0.1")
    mysql_port = int(MYSQL.get("port", 3306))
    mysql_user = MYSQL.get("user", "root")
    mysql_password = MYSQL.get("password", "")
    mysql_database = MYSQL.get("database", "qq_bridge_kb")

    allowed_ips = [ip.strip() for ip in str(WEB.get("allowedIps", "")).split(",") if ip.strip()]
    debug = os.environ.get("QQ_CONSOLE_DEBUG") == "1"


settings = Settings()
