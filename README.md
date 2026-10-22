# QQ ↔ DeepSeek Harness 桥接（重构版）

把 DeepSeek Harness（DSH）驱动的 AI 接进 QQ 群/私聊：收发消息、群聊唤醒、知识库/黑话、峰谷策略、收藏表情、语音，并提供一个统一的 Flask 管理控制台。

> 本版本经过一次大重构：配置改为 **TOML**，管理界面统一为 **Flask + JWT**（纯 HTTP），知识库/黑话并入主项目，群聊/私聊分离，新增峰谷多时段策略。旧 `public/console.html` 仍保留在仓库里供历史测试使用，但**不再对外提供**（访问桥接 `http://127.0.0.1:3100/` 会 302 跳转到 Flask 控制台）。

## 架构

```
QQ ←→ SnowLuma(OneBot WS)   Node 桥接 (src/bridge.js, 3100 仅回环)
                                │  ├─ /api/...       给 MCP 工具（AI 自己用）
                                │  └─ /internal/...  给 Flask 控制台（control token）
                                ▼
                          DSH (3080) ── 会话 / 工具调用
                                ▲
                     Flask 控制台 (web/, 21001) ── JWT + CSRF
                                │
                          MySQL qq_bridge_kb（知识库 / 黑话 / 用户）
```

- **桥接**：消息接入、唤醒判定、发送、知识库/黑话注入、峰谷策略、表情/语音。
- **Flask 控制台**：唯一的浏览器入口（登录、会话、唤醒、峰谷、知识库、黑话、工具开关、人格、预设、令牌、日志、用户、表情）。
- **MCP 工具**：AI 在 QQ 里调用 `qq_*` 工具；控制台不参与这条链路。

## 快速开始

前置：Node ≥ 22、Python 3.12、MySQL 8、SnowLuma（OneBot 网关）、DSH。

```powershell
cd E:\qq-bridge

# 1) 依赖
npm install
python -m venv web\.venv
web\.venv\Scripts\python -m pip install -r web\requirements.txt

# 2) 配置（首次从模板复制，按需修改）
copy config.example.toml config.toml
notepad config.toml          # 至少填 ownerQQ / allow / consoleToken / kb.mysql
# 旧 JSON 配置可一键迁移（自动备份 + 校验）：
node scripts/migrate-config.mjs

# 3) 一键启动桥接 + 控制台（已在跑的自动跳过）
start-all.bat（桥接开窗口；控制台无窗口，日志写 state\web-console.log）

#    也可以分别启动：
#    node src\bridge.js       桥接（或 start.bat 循环守护）
#    web\run.bat             控制台（窗口内可见日志；退出后自动关闭）
```

浏览器打开 **http://127.0.0.1:21001/**，用 `kb_user` 表里的账号登录（初始 admin 由 `migrate.py`/旧 kb-admin 创建；也可在控制台"用户"页新建）。

## 配置（config.toml）

TOML 是唯一权威配置；`config.json` 只是过渡期自动生成的镜像（供尚未迁移的脚本读取，可忽略）。程序保存（token 自愈、控制台改设置）会重新序列化 TOML——**手写注释可能丢失**，重要说明请写进文档。

关键段：

| 段 | 说明 |
| --- | --- |
| `ownerQQ` / `allow` / `deny` | 管理员 QQ、群/私聊白名单 |
| `consoleUrl` / `consoleToken` / `consoleAllowedHosts` | 桥接控制台监听地址与令牌（默认只监听回环） |
| `[dsh]` | DSH 地址、模型、默认推理强度 |
| `[web]` | Flask 控制台绑定/端口（默认 `0.0.0.0:21001`）、`bridgeUrl`、会话时长 |
| `[kb]` / `[slang]` | 知识库 MySQL 与黑话库开关 |
| `[socialV2.wake]` | 唤醒默认参数（合批窗口、沉睡前观察、推荐关键词） |
| `[[periods]]` | **峰谷时段策略**（见下） |

峰谷示例：

```toml
[[periods]]
name = "低谷"
start = "00:30"
end = "08:30"
replyProbability = 0.9
reasoningEffort = "low"
proactive = true

[[periods]]
name = "高峰"
start = "08:30"
end = "00:30"
replyProbability = 0.35
reasoningEffort = "high"
proactive = false
sendMaxPerHour = 30
```

- 任意多段，按顺序匹配，第一条命中即生效；支持跨零点（`22:00 → 06:00`）。
- 可覆盖：`replyProbability`、`reasoningEffort`、`model`、`proactive`、`sendMaxPerMinute/Hour`；留空 = 用全局默认。
- 改完在控制台 `/periods` 保存会热重载，**下一轮唤醒生效**，无需重启。

## 群聊 / 私聊

- **群聊**：按唤醒配置（@、名字、关键词、提问、拍一拍、概率）决定是否回复；有合批窗口（默认 8s）、潜水/主动检查。
- **私聊**：收到消息**立即回复**（合批 0ms），不排主动检查、不进潜水状态机。
- **管理员私聊**：AI 额外拥有 `qq_admin_config` 工具，可以 `get/set/reload` 配置（只允许白名单字段，改完热重载）。

## 知识库与黑话

- 知识库：`kb_entry`，关键词命中时注入（≤2 条 / 800 字），也可让 AI 用 `qq_kb_search` 主动查。
- 黑话：`kb_slang`，确认后的词条会进入唤醒提示；支持 AI 抽取候选 + 控制台审核。
- 控制台页面：`/kb`（含注入预览）、`/slang`、`/revisions`；数据与旧 kb-admin 完全兼容。

## 安全

- 浏览器只访问 Flask（21001），桥接控制台（3100）只监听回环，令牌不进浏览器。
- 登录：`kb_user` + werkzeug PBKDF2；JWT 放 HttpOnly Cookie，写操作校验 CSRF。
- 明确**只用 HTTP**（自签 HTTPS 会被浏览器拦截）；远程访问请用 SSH 隧道或在反代加 TLS。
- 建议：`web.allowedIps` 限制来源、`consoleAllowedHosts` 只填必要域名、定期轮换 `consoleToken`。

## 目录

```
src/            Node 桥接（bridge.js、config-store.js、periods.js、kb-mysql.js、slang-db.js…）
web/            Flask 控制台（app.py、views/、templates/、static/、selftest*.py）
state/          运行时（会话、表情库、黑话语义镜像、日志；gitignore）
config.toml     权威配置（gitignore；模板 config.example.toml）
docs/           文档（guides/DEPLOY.md 部署、guides/KNOWLEDGE_BASE.md 知识库）
scripts/        测试、探针、运维脚本
```

## 测试

```powershell
npm run test:audit            # Node 全量审计
node scripts/test-periods.mjs # 峰谷纯函数
cd web
.venv\Scripts\python selftest.py       # 控制台离线自检（登录/CSRF/页面）
.venv\Scripts\python selftest_kb.py    # 知识库/黑话 CRUD（真库，自动清理）
.venv\Scripts\python selftest_toml.py  # 配置定向改写
```

## 部署

见 **[docs/guides/DEPLOY.md](docs/guides/DEPLOY.md)**：依赖、MySQL 初始化、DSH/SnowLuma 配置、开机自启（任务计划程序）、备份与排障。

## 变更摘要（本次重构）

1. 配置 JSON → **TOML**（`config-store.js` 统一读写，迁移脚本 + JSON 过渡镜像）。
2. 统一控制台：**Flask + JWT + CSRF**，12 个页面，替代 240KB 单文件旧控制台。
3. 知识库/黑话从独立 `qq-kb-admin` **并入** `web/`。
4. 群聊/私聊分离：私聊即时回复、无周期检查。
5. **峰谷多时段策略**（回复概率/推理强度/模型/主动检查/发送限频）。
6. 管理员私聊可用 `qq_admin_config` 改配置并热重载。
