"""MySQL 访问：复用知识库所在的库（qq_bridge_kb），只读用户表用于登录。

刻意不引入 ORM：PyMySQL + 显式 SQL，短小、可控、与现有 kb-admin 的表结构一致。
"""

from __future__ import annotations

import pymysql
from flask import g

from settings import settings


def connect() -> pymysql.connections.Connection:
    return pymysql.connect(
        host=settings.mysql_host,
        port=settings.mysql_port,
        user=settings.mysql_user,
        password=settings.mysql_password,
        database=settings.mysql_database,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        connect_timeout=5,
        read_timeout=10,
        write_timeout=10,
    )


def get_db() -> pymysql.connections.Connection:
    """每请求一个连接，请求结束由 close_db 关闭。"""
    if "db" not in g:
        g.db = connect()
    return g.db


def close_db(_exc=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query(sql: str, params=(), one: bool = False):
    with get_db().cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return (rows[0] if rows else None) if one else rows


def execute(sql: str, params=()) -> int:
    with get_db().cursor() as cur:
        cur.execute(sql, params)
        return cur.rowcount


def insert(sql: str, params=()) -> int:
    with get_db().cursor() as cur:
        cur.execute(sql, params)
        return int(cur.lastrowid or 0)


def init_app(app) -> None:
    app.teardown_appcontext(close_db)
