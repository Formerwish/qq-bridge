# 第五人格知识库 · 管理端（qq-kb-admin）

给 **QQ 桥接（qq-bridge）** 用的第五人格知识库后台：你用浏览器录条目，AI 在群里聊天时按关键词**按需**读到资料，并能用 `qq_kb_search` 主动查。

- 后端：Python 3.12 + Flask + PyMySQL
- 数据库：MySQL 8.4（库名 `qq_bridge_kb`，**和桥接共用**）
- 前端：服务端渲染的 Jinja2 页面 + 一点原生 JS，没有构建步骤
- 默认地址：`http://127.0.0.1:3210/`（监听地址/端口在 `config.json` 里改）

## 和桥接怎么配合

```
你/普通用户在浏览器改 kb_entry（本后台）
        │  最多 60 秒（桥接关键词缓存 TTL）
        ▼
桥接收到群消息 → 命中关键词 → 查库取正文 → 注入提示词（≤2 条、≤800 字）
                              └ 没命中就完全不注入、不查库
AI 不确定时 → qq_kb_search("机械师 BLK.TRACY") → 全文检索返回标题+摘要
```

- 桥接侧配置在 `E:\qq-bridge-0.2.0-r4\config.json` 的 `kb` 段（默认只读账号、`cacheTtlMs: 60000`）。
- 桥接**只读**：它只会 `SELECT`，不会写库；写权限只在本后台。
- 改完条目**不需要重启桥接**；改 `config.json` 才需要重启。

## 首次部署

```bat
cd /d E:\qq-kb-admin
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt

copy config.example.json config.json   :: 已有 config.json 就跳过，检查 mysql 段
.venv\Scripts\python.exe migrate.py    :: 建表 + 创建初始 admin（会打印随机密码）
.venv\Scripts\python.exe seed.py       :: 可选：写入 22 条第五人格种子数据
```

之后双击 `run.bat`（会自动建 venv/装依赖/起服务），或者：

```bat
.venv\Scripts\python.exe app.py
```

## 账号与权限

| 角色 | 能做什么 |
| --- | --- |
| `admin` | 全部：条目增删改、启停、管用户（建号/禁用/改角色/重置密码）、看修订日志 |
| `editor` | 条目新增、编辑、启停；不能删条目、不能管用户 |

- 初始管理员由 `migrate.py` 创建（用户名 `admin`，密码在控制台打印，只显示一次）。
- 登录后右上角「用户」页建普通用户，把用户名/密码发给对方即可。
- 密码用 werkzeug 的 PBKDF2 哈希存库；登录失败 5 分钟内 8 次会被临时锁定。
- 改密码：首页底部「改我的密码」。

## 数据表

| 表 | 作用 |
| --- | --- |
| `kb_entry` | 知识条目：`topic / title / keywords / body / priority / enabled / created_by / updated_by / updated_at`；`title+body` 上有 **ngram 全文索引**（中文检索） |
| `kb_user` | 后台账号：`username / password_hash / role / enabled / last_login_at` |
| `kb_revision` | 修订日志：每次新增/修改/启停/删除都记一条，含改前改后 JSON 和操作人 |

`keywords` 是桥接唯一的分发依据：用逗号分隔，把常见叫法/别称/黑话都写进去（单个关键词至少 2 个字）。

## 安全须知

1. **别把 root 给后台**。`config.json` 里填的是只读业务账号（当前 `qqkb_ro`，仅 `qq_bridge_kb` 库的权限就够）。
2. 默认监听 `0.0.0.0:3210`，方便局域网内的授权用户访问。**如果你要开给公网**，请套一层 HTTPS 反向代理（Nginx/Caddy），并在防火墙只放行 3210 给可信来源；本项目自带的是明文 HTTP + 会话 Cookie。
3. 会话密钥：首次启动若 `server.secretKey` 为空，会自动生成并写回 `config.json`（否则每次重启都会把所有人踢下线）。
4. 所有 SQL 均为参数化；页面不提供「执行 SQL」入口。
5. 写入有审计：删条目也只删行、日志保留（`kb_revision`）。

## 常见问题

| 现象 | 处理 |
| --- | --- |
| 启动报「连不上 MySQL」 | 检查 `config.json` 的 host/port（本机 MySQL 是 **10708**）、账号密码、服务是否在跑 |
| 页面能开但登录失败 | 没跑 `migrate.py`（没有用户表），或密码错；重新 `migrate.py` 会打印新 admin 密码（已有用户时会跳过） |
| 桥接不注入 | ① 条目 `enabled=1`；② 消息里出现了关键词（≥2 字、子串匹配）；③ 桥接日志有没有 `[kb]` 报错；④ 改完等 60 秒 |
| `qq_kb_search` 报未启用 | 桥接 `config.json` 的 `socialV2.tools.kbSearch` 是否为 `true`（默认 true），并重启桥接/DSH |
| 全文搜不到中文 | 确认 `ft_kb` 索引存在（`migrate.py` 会补）；ngram 最小切词是 2 字，单字搜不到 |

## 文件

```
app.py          Flask 主程序（路由/鉴权/CSRF/条目与用户管理）
db.py           连接与查询封装（PyMySQL，全部参数化）
migrate.py      幂等建表 + 初始 admin
seed.py         种子数据（22 条，幂等）
config.json     本机配置（含数据库凭据，别提交到公开仓库）
templates/      base / login / index / edit / entry / match / users / revisions / error
static/style.css
run.bat         一键启动
```

---

## 黑话库（kb_slang）

桥接的「黑话学习」也改成存 MySQL 了，本后台对应页签是 **黑话**：

- 桥接自动学习出来的词条是 `candidate`（候选），**只有 `confirmed` 会注入 AI 提示词**
- 页面可以一键 确认 / 拒绝 / 转候选、编辑含义/用法/例句、手动新增、删除（admin）
- 每条能看到学习证据（哪个群、谁说的、原文）和修订记录
- 顶部两个按钮直接遥控桥接学习：`触发抽取学习`（/api/slang/extract）、`研究候选`（/api/slang/research）
  —— 需要 `config.json` 里配好 `bridge.consoleUrl` / `bridge.consoleToken`，且桥接在运行

首次把现有 JSON 黑话导进库：

```bat
.venv\Scripts\python.exe migrate.py --no-admin   :: 建 kb_slang / kb_slang_revision
.venv\Scripts\python.exe import_slang.py         :: 导入 ..\qq-bridge-0.2.0-r4\state\slang.json
```

冲突规则：桥接和管理端都用 `updated_ms` 判断新旧，**谁改得晚听谁的**；桥接每 60 秒拉一次后台的改动。
`usage` 是 MySQL 保留字，SQL 里必须写成 `` `usage` ``（改代码时别手滑去掉反引号）。
## 修订日志（kb_revision / kb_slang_revision）

两张表都是**纯审计日志**：AI 不读、桥接不读，删掉不影响任何功能。

| 表 | 内容 |
| --- | --- |
| `kb_revision` | 知识条目：create / update / enable / disable / delete，含 `before_json` / `after_json`、操作人、时间 |
| `kb_slang_revision` | 黑话：create / update / confirm / reject / candidate / delete（桥接学习产生的候选不写这里，只有后台操作写） |

「目标已被删除、日志还留着」的记录会在这里显形（页面点进去 404）。清理：

```bat
.venv\Scripts\python.exe prune_revisions.py --dry-run   :: 先看数量
.venv\Scripts\python.exe prune_revisions.py             :: 只删无主记录
.venv\Scripts\python.exe prune_revisions.py --days 90   :: 顺带删 90 天前的
```

想长期保留审计就别定期跑；只想留最近半年就加 `--days 180` 挂个计划任务。种子数据（`seed.py`）和黑话导入（`import_slang.py`）**不写**修订日志，不会制造噪音。