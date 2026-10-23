# 知识库与黑话库

知识库用于让 AI 了解第五人格的角色、皮肤、赛事与术语；黑话库记录群聊常用梗。两者都存在 MySQL，按需注入提示词，避免每轮白烧 token。

## 1. 数据表

| 表 | 用途 | 主要字段 |
| --- | --- | --- |
| `kb_entry` | 知识条目 | `title`、`content`、`keywords`、`enabled`、时间戳 |
| `kb_slang` | 黑话词条 | `content`、`meaning`、`usage`、`status`（candidate/confirmed/rejected）、`sources` |
| `kb_user` | 控制台账号 | `username`、`password_hash`（明文）、`role`、`enabled` |
| `kb_revision` | 条目修订记录 | 条目 id、动作、变更前后内容、操作者、时间 |

数据库名由 `config.toml` 的 `kb.mysql.database` 指定；账号只需读写上述表。

## 2. 配置

```toml
[kb]
enabled = true
cacheTtlMs = 60000

[kb.mysql]
host = "127.0.0.1"
port = 3306
user = "qqkb_bridge"
password = "***"
database = "qq_bridge_kb"

[kb.inject]
enabled = true
maxEntries = 2
maxChars = 800

[kb.query]
maxResults = 5
previewChars = 400
timeoutMs = 2500
```

- `kb.inject`：群消息命中关键词时，最多注入几条、多少字；
- `kb.query`：AI 调用 `qq_kb_search` 时的返回上限与超时；
- 数据库异常时按 fail-open 处理（不注入、不阻断聊天），并记录日志。

## 3. 注入与检索

- 关键词命中：桥接把当前消息与条目关键词匹配，命中后按相关度取前 `maxEntries` 条拼进提示词；
- AI 主动查：工具 `qq_kb_search(q)`，返回标题 + 摘要；
- 黑话：`qq_slang_query` 查询已确认词条，`qq_slang_submit` 提交候选，管理员在控制台确认；
- 唤醒提示词里的黑话表只放已确认词条，按出现次数排序。

## 4. 管理界面

控制台提供：

| 页面 | 用途 |
| --- | --- |
| `/kb` | 知识条目列表、搜索、新建、编辑、停用、删除 |
| `/kb/preview` | 输入一段话，预览会命中哪些条目、注入什么内容 |
| `/slang` | 黑话候选/已确认/已拒绝列表，确认、拒绝、编辑、删除 |
| `/revisions` | 知识库修订记录 |

编辑者（editor）角色只能访问知识库与黑话页面。

## 5. 初始化与运维

```powershell
cd web
.venv\Scripts\python management\migrate.py     # 建表
.venv\Scripts\python management\seed.py        # 初始数据（可选）
.venv\Scripts\python management\import_slang.py # 导入黑话 JSON
```

迁移脚本会读取 `web/management/config.example.json` 里的连接配置；实际部署请复制为 `config.json` 并填写。

## 6. 验证

```powershell
node scripts/test-kb.mjs        # 知识库检索与注入
node scripts/test-slang-db.mjs  # 黑话库
```

桥接侧的数据库实现见 `src/kb-mysql.js`、`src/slang-db.js`；控制台侧见 `web/kb_common.py`。
