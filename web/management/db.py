"""数据库连接与通用查询封装（PyMySQL）。

设计：
- 每次请求一个连接（Flask g），请求结束自动关闭；本项目写入频率很低，够用。
- 所有 SQL 全部参数化；本文件不接收任何来自前端的 SQL 片段。
- 连接失败抛出 DatabaseError，由调用方转成人话页面，而不是 500 堆栈。
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager

import pymysql
from pymysql.cursors import DictCursor

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

DEFAULT_LIMITS = {"titleMax": 128, "keywordsMax": 255, "bodyMax": 5000, "topicMax": 32}


class DatabaseError(RuntimeError):
    pass


def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        raise SystemExit(
            f"缺少配置文件 {CONFIG_PATH}\n"
            "请复制 config.example.json 为 config.json，并填好 mysql 连接信息。"
        )
    with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
        cfg = json.load(fh)
    cfg.setdefault("server", {})
    cfg.setdefault("mysql", {})
    limits = dict(DEFAULT_LIMITS)
    limits.update(cfg.get("limits") or {})
    cfg["limits"] = limits
    return cfg


def save_config(cfg: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, ensure_ascii=False, indent=2)


def connect(cfg: dict | None = None):
    cfg = cfg or load_config()
    my = cfg["mysql"]
    try:
        return pymysql.connect(
            host=my.get("host", "127.0.0.1"),
            port=int(my.get("port", 3306)),
            user=my.get("user", ""),
            password=my.get("password", ""),
            database=my.get("database", "qq_bridge_kb"),
            charset=my.get("charset", "utf8mb4"),
            cursorclass=DictCursor,
            autocommit=False,
            connect_timeout=5,
            read_timeout=15,
            write_timeout=15,
        )
    except pymysql.MySQLError as exc:
        raise DatabaseError(f"连不上 MySQL（{my.get('host')}:{my.get('port')}）：{exc}") from exc


@contextmanager
def get_db():
    conn = connect()
    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception:
            pass


def query(sql: str, params=(), one: bool = False):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            conn.commit()
    if one:
        return rows[0] if rows else None
    return rows


def execute(sql: str, params=()) -> int:
    """执行写操作，返回 lastrowid（INSERT）或影响行数（UPDATE/DELETE 时为 rowcount）。"""
    with get_db() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                last_id = cur.lastrowid
                affected = cur.rowcount
            conn.commit()
            return last_id if sql.strip().lower().startswith("insert") else affected
        except Exception:
            conn.rollback()
            raise


def table_exists(name: str) -> bool:
    row = query(
        "SELECT COUNT(*) AS n FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s",
        (name,),
        one=True,
    )
    return bool(row and int(row["n"]) > 0)


def column_exists(table: str, column: str) -> bool:
    row = query(
        "SELECT COUNT(*) AS n FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s",
        (table, column),
        one=True,
    )
    return bool(row and int(row["n"]) > 0)
