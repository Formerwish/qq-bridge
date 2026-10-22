# 知识库管理脚本（从旧 kb-admin 项目合并进来）

这些是**一次性/运维脚本**，页面功能已经合并进主控制台（`web/` 的 `/kb`、`/slang`、`/users`），
平时不需要运行它们。保留的原因：新环境建表、导入旧数据、清理修订记录。

| 脚本 | 用途 |
| --- | --- |
| `migrate.py` | 建 5 张表（kb_entry / kb_user / kb_revision / kb_slang / kb_slang_revision）+ 初始 admin |
| `seed.py` | 写入 22 条第五人格种子知识 |
| `import_slang.py` | 从 `state/slang.json` 导入黑话到 `kb_slang` |
| `prune_revisions.py` | 清理过旧修订记录 |
| `e2e_test.py` | 旧版页面的端到端冒烟（已过时，仅作参考） |

## 用法

```powershell
cd E:\qq-bridge\web\management
copy config.example.json config.json   # 填 MySQL 连接（与 config.toml 的 [kb.mysql] 一致）
..\.venv\Scripts\python.exe migrate.py --admin-password "你的密码"
..\.venv\Scripts\python.exe seed.py
```

说明：
- 脚本自带 `db.py`（读本目录的 `config.json`），不依赖主控制台的 `settings.py`；
- 已有库不要重复跑 `migrate.py`（建表用 `IF NOT EXISTS`，但初始 admin 只在表空时创建）；
- `config.json` 含数据库密码，**不要提交到 git**（本目录已在 `.gitignore` 的 `config.json` 规则内）。
