"""建表 / 升级表结构（幂等，可反复执行）。

用法：
    python migrate.py                       # 建表 + 若没有任何用户则创建 admin（随机密码）
    python migrate.py --admin-password 123  # 指定初始管理员密码
    python migrate.py --no-admin            # 只建表

表结构说明见 README.md。
"""

from __future__ import annotations

import argparse
import secrets
import string

from werkzeug.security import generate_password_hash

from db import DatabaseError, column_exists, execute, get_db, load_config, query, table_exists

CREATE_ENTRY = """
CREATE TABLE IF NOT EXISTS kb_entry (
  id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  topic       VARCHAR(32)  NOT NULL DEFAULT '第五人格' COMMENT '分类：角色/皮肤/赛事/术语/地图',
  title       VARCHAR(128) NOT NULL COMMENT '展示给 AI 的标题',
  keywords    VARCHAR(255) NOT NULL COMMENT '逗号分隔，命中即注入',
  body        TEXT         NOT NULL COMMENT '正文，纯文本 200~600 字最佳',
  priority    TINYINT      NOT NULL DEFAULT 0 COMMENT '越大越优先',
  enabled     TINYINT(1)   NOT NULL DEFAULT 1,
  created_by  VARCHAR(64)  NOT NULL DEFAULT '',
  updated_by  VARCHAR(64)  NOT NULL DEFAULT '',
  created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FULLTEXT KEY ft_kb (title, body) WITH PARSER ngram
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
"""

CREATE_USER = """
CREATE TABLE IF NOT EXISTS kb_user (
  id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  username      VARCHAR(64)  NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  role          ENUM('admin','editor') NOT NULL DEFAULT 'editor',
  enabled       TINYINT(1)   NOT NULL DEFAULT 1,
  created_by    VARCHAR(64)  NOT NULL DEFAULT '',
  created_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_login_at TIMESTAMP    NULL DEFAULT NULL,
  UNIQUE KEY uk_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
"""

CREATE_REVISION = """
CREATE TABLE IF NOT EXISTS kb_revision (
  id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  entry_id    BIGINT UNSIGNED NULL,
  action      ENUM('create','update','delete','enable','disable') NOT NULL,
  title       VARCHAR(128) NOT NULL DEFAULT '',
  before_json MEDIUMTEXT NULL,
  after_json  MEDIUMTEXT NULL,
  actor       VARCHAR(64) NOT NULL DEFAULT '',
  created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_entry (entry_id),
  KEY idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
"""

# 黑话库：桥接的学习器会往里写候选（candidate），后台确认后变 confirmed 才会注入提示词。
CREATE_SLANG = """
CREATE TABLE IF NOT EXISTS kb_slang (
  id                   VARCHAR(40)  NOT NULL PRIMARY KEY,
  content              VARCHAR(64)  NOT NULL COMMENT '黑话原文，唯一',
  meaning              VARCHAR(255) NOT NULL DEFAULT '',
  `usage`                VARCHAR(255) NOT NULL DEFAULT '',
  example              VARCHAR(255) NOT NULL DEFAULT '',
  risk                 VARCHAR(255) NOT NULL DEFAULT '',
  status               ENUM('candidate','confirmed','rejected') NOT NULL DEFAULT 'candidate',
  source               VARCHAR(16)  NOT NULL DEFAULT 'ai',
  count                INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '出现/引用次数',
  sources_json         TEXT NULL,
  evidence_json        TEXT NULL COMMENT '证据（群/说话人/原文/时间），桥接写入',
  last_inference_count INT UNSIGNED NOT NULL DEFAULT 0,
  created_ms           BIGINT NOT NULL DEFAULT 0,
  updated_ms           BIGINT NOT NULL DEFAULT 0 COMMENT '毫秒时间戳：桥接与后台用它判定谁更新更晚',
  created_at           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_content (content),
  KEY idx_status (status),
  KEY idx_updated_ms (updated_ms)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
"""

CREATE_SLANG_REVISION = """
CREATE TABLE IF NOT EXISTS kb_slang_revision (
  id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  slang_id    VARCHAR(40) NOT NULL,
  action      ENUM('create','update','confirm','reject','candidate','delete','learn') NOT NULL,
  content     VARCHAR(64) NOT NULL DEFAULT '',
  before_json MEDIUMTEXT NULL,
  after_json  MEDIUMTEXT NULL,
  actor       VARCHAR(64) NOT NULL DEFAULT '',
  created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_slang (slang_id),
  KEY idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
"""


def ensure_fulltext_index() -> None:
    rows = query(
        "SELECT INDEX_NAME FROM information_schema.STATISTICS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'kb_entry' AND INDEX_NAME = 'ft_kb' "
        "LIMIT 1"
    )
    if rows:
        return
    execute("ALTER TABLE kb_entry ADD FULLTEXT KEY ft_kb (title, body) WITH PARSER ngram")


def ensure_columns() -> None:
    if not column_exists("kb_entry", "created_by"):
        execute("ALTER TABLE kb_entry ADD COLUMN created_by VARCHAR(64) NOT NULL DEFAULT ''")
    if not column_exists("kb_entry", "updated_by"):
        execute("ALTER TABLE kb_entry ADD COLUMN updated_by VARCHAR(64) NOT NULL DEFAULT ''")
    if not column_exists("kb_entry", "created_at"):
        execute("ALTER TABLE kb_entry ADD COLUMN created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP")


def random_password(length: int = 14) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def ensure_admin(password: str | None) -> None:
    row = query("SELECT COUNT(*) AS n FROM kb_user", one=True)
    if row and int(row["n"]) > 0:
        print("已有用户，跳过初始管理员创建。")
        return
    pwd = password or random_password()
    execute(
        "INSERT INTO kb_user (username, password_hash, role, enabled, created_by) VALUES (%s, %s, 'admin', 1, 'migrate')",
        ("admin", generate_password_hash(pwd)),
    )
    print("=" * 56)
    print("  已创建管理员账号")
    print("  用户名: admin")
    print(f"  密  码: {pwd}")
    print("  （登录后可在「用户」页改密码 / 加普通用户）")
    print("=" * 56)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--admin-password", default=None)
    parser.add_argument("--no-admin", action="store_true")
    args = parser.parse_args()

    cfg = load_config()
    print(f"目标数据库：{cfg['mysql']['host']}:{cfg['mysql']['port']}/{cfg['mysql']['database']}")

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                for ddl in (CREATE_ENTRY, CREATE_USER, CREATE_REVISION, CREATE_SLANG, CREATE_SLANG_REVISION):
                    cur.execute(ddl)
            conn.commit()
        print("表结构已就绪（kb_entry / kb_user / kb_revision / kb_slang / kb_slang_revision）。")

        ensure_columns()
        ensure_fulltext_index()
        print("字段与 ngram 全文索引已确认。")

        if not args.no_admin:
            ensure_admin(args.admin_password)

        for table in ("kb_entry", "kb_user", "kb_revision", "kb_slang", "kb_slang_revision"):
            assert table_exists(table), f"表 {table} 创建失败"
    except DatabaseError as exc:
        raise SystemExit(f"数据库错误：{exc}") from exc


if __name__ == "__main__":
    main()
