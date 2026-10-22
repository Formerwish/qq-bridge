"""控制台密码：以明文存储并做常量时间比较。

- 用户表 password_hash 字段直接存明文密码；
- 登录时用常量时间比较明文；
- 哈希格式（pbkdf2:/scrypt:/argon2: 前缀）的记录一律拒绝登录，
  并提示管理员在「用户」页重置密码。

⚠️ 安全提示：任何能读数据库/备份的人都能直接看到所有控制台密码。
   仅建议在本机、单人使用且数据库不对外的场景使用。
"""

from __future__ import annotations

import hmac

_HASH_PREFIXES = ("pbkdf2:", "scrypt:", "argon2:")


def is_legacy_hash(stored: str) -> bool:
    return str(stored or "").startswith(_HASH_PREFIXES)


def make_password(password: str) -> str:
    """明文直接落库。"""
    return str(password or "")


def verify_password(stored: str, supplied: str) -> bool:
    stored = str(stored or "")
    if not stored or is_legacy_hash(stored):
        return False
    return hmac.compare_digest(stored, str(supplied or ""))


def display_password(stored: str) -> str | None:
    """给管理端展示：明文原样返回；旧哈希不展示。"""
    if not stored or is_legacy_hash(stored):
        return None
    return str(stored)
