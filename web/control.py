"""访问桥接的最小控制面（/internal/*）。

浏览器永远不直接访问桥接：Flask 在服务端带 `x-control-token` 调用 127.0.0.1:3100。
失败时返回结构化错误，页面降级显示"桥接离线"，而不是 500。
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from settings import settings


class BridgeError(RuntimeError):
    pass


def _request(path: str, method: str = "GET", body: dict | None = None, timeout: float = 5.0):
    url = f"{settings.bridge_url}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("x-control-token", settings.control_token or "")
    # 桥接的 /api/* 管理端点只认 x-console-token（同一令牌），两种头都带上。
    req.add_header("x-console-token", settings.control_token or "")
    if data is not None:
        req.add_header("content-type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "ignore")[:200]
        except Exception:
            pass
        raise BridgeError(f"桥接返回 {exc.code}：{detail or exc.reason}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise BridgeError(f"桥接不可达（{settings.bridge_url}）：{exc}") from exc


def status() -> dict:
    return _request("/internal/status")


def sessions() -> dict:
    return _request("/internal/sessions")


def health() -> bool:
    try:
        return bool(_request("/internal/health", timeout=2).get("ok"))
    except BridgeError:
        return False


def session(key: str) -> dict:
    return _request(f"/internal/sessions/{key}")


def pause(paused: bool) -> dict:
    return _request("/internal/pause", method="POST", body={"paused": paused})


def mark_read(key: str) -> dict:
    return _request("/internal/mark-read", method="POST", body={"key": key})


def set_wake(key: str, config: dict) -> dict:
    return _request("/internal/wake", method="POST", body={"key": key, "config": config})


def reload_config() -> dict:
    return _request("/internal/reload", method="POST", body={})


def logs(lines: int = 200) -> dict:
    return _request(f"/internal/logs?lines={int(lines)}")


def periods() -> dict:
    return _request("/internal/periods")


def admin_post(path: str, body: dict | None = None) -> dict:
    """调用桥接的管理端点（服务端持 consoleToken）。"""
    return _request(path, method="POST", body=body or {}, timeout=120)


def roles() -> dict:
    return _request("/internal/roles")


def role(name: str) -> dict:
    return _request(f"/internal/role?name={urllib.parse.quote(name)}")


def save_role(name: str, content: str) -> dict:
    return _request("/internal/role", method="POST", body={"name": name, "content": content}, timeout=30)


def set_current_role(name: str) -> dict:
    return _request("/internal/role/current", method="POST", body={"name": name})


def presets() -> dict:
    return _request("/internal/presets")


def stickers() -> dict:
    return _request("/internal/stickers")


def sticker_note(sticker_id: str, local_note: str, tags: list[str]) -> dict:
    return _request("/internal/stickers/note", method="POST",
                    body={"id": sticker_id, "localNote": local_note, "tags": tags})


def sticker_favorite(sticker_id: str, favorite: bool) -> dict:
    return _request("/internal/stickers/note", method="POST", body={"id": sticker_id, "favorite": bool(favorite)})


def sticker_sync() -> dict:
    return _request("/internal/stickers/sync", method="POST", body={}, timeout=180)


def reset_session(key: str) -> dict:
    """重置会话上下文：删掉桥接里的 DSH 会话映射，下一条消息会新建 DSH 会话。"""
    return _request("/api/session/reset", method="POST", body={"key": key}, timeout=30)


def sticker_image(sticker_id: str) -> tuple[bytes, str]:
    """原始表情图片（保留动图）；缓存由 views/stickers.py 负责。"""
    url = f"{settings.bridge_url}/internal/stickers/image?id={urllib.parse.quote(sticker_id)}"
    req = urllib.request.Request(url)
    req.add_header("x-control-token", settings.control_token or "")
    req.add_header("x-console-token", settings.control_token or "")
    with urllib.request.urlopen(req, timeout=20) as resp:
        ctype = (resp.headers.get("content-type") or "image/gif").split(";")[0]
        return resp.read(), ctype


def config_get() -> dict:
    return _request("/internal/config")


def config_update(updates: dict) -> dict:
    return _request("/internal/config", method="POST", body={"updates": updates})


def config_full() -> dict:
    return _request("/internal/config-full", timeout=10)


def config_save(updates: dict) -> dict:
    return _request("/internal/config-full", method="POST", body={"updates": updates}, timeout=15)
