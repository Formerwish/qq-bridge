# 重构计划（v1）

> 状态：**P0、P1 已完成**（配置 TOML + Flask 骨架/登录/概览）。本文是后续阶段的施工图，方案已由用户拍板。
> 目标：管理面全部迁到 Flask、删掉旧单文件控制台、配置改 TOML、群聊/私聊分离、峰谷多段策略、知识库并入主项目。

## 0. 已拍板的决策

| 决策 | 选择 |
| --- | --- |
| 控制台实现 | **管理逻辑全搬进 Flask**（桥接只保留引擎 + 最小控制面） |
| 旧 `public/console.html` | **删除**（不再保留应急入口） |
| TOML 解析 | Node 用 `smol-toml`（零依赖小库）；Python 用内置 `tomllib`，写用模板 |
| 峰谷时段 | **任意多段**（`[[periods]]` 列表，每段含时段 + 覆盖项） |
| 鉴权 | JWT（HttpOnly Cookie）+ CSRF 双提交；纯 HTTP，不做自签 HTTPS |
| 新增依赖 | 仅 `smol-toml`（Node）、`PyJWT`（Python）；不引入前端框架/AntD |

## 1. 目标架构

```
E:\qq-bridge\
├── src\                  # Node 桥接（引擎：收发 / 唤醒 / 学习 / DB / 峰谷套用）
│   ├── bridge.js
│   └── control-api.js    # 新增：最小控制面（~20 个 /internal/* 端点，仅 127.0.0.1 + controlToken）
├── config.toml           # 唯一权威配置（含 [[periods]]、admin、console）
├── web\                  # 新统一控制台（Flask，唯一对外入口，默认 3210）
│   ├── app.py            # 工厂 + 蓝图 + JWT + CSRF
│   ├── config.py         # tomllib 读取 + 安全写入（保留注释的定向改写）
│   ├── control.py        # 调桥接 control-api（服务端持 controlToken）
│   ├── db.py             # PyMySQL（复用 qq_bridge_kb）
│   ├── auth.py           # 登录 / 密码哈希 / 权限
│   ├── views\            # auth dashboard sessions wake periods kb slang stickers
│   │                     # roles presets tools tokens logs users
│   ├── templates\        # Jinja，服务端渲染
│   └── static\           # app.css + app.js（无框架）
└── state\                # 运行时（不变）
```

**浏览器只访问 Flask**；桥接控制台（3100）只监听 `127.0.0.1`，Flask 用 `controlToken` 调用，token 不进浏览器。

## 2. 关键设计

### 2.1 控制面切分（"管理逻辑全搬进 Flask"的落地边界）

| 归属 | 内容 |
| --- | --- |
| **Flask 直接做** | 配置读写（TOML）、知识库/黑话/表情库/用户的增删改查、峰谷策略编辑、令牌花费统计展示、日志浏览、鉴权与权限 |
| **Flask → 桥接 control-api** | 需要运行时状态的：会话列表/详情、唤醒配置、标记已读、测试发送、重启、暂停、切换模式/预设、热重载、工具开关、人格注入预览 |
| **桥接保留给 MCP** | `qq_*` 工具用的 agent API（unread/send/wake-config/mark-read/sticker-image/kb-search…）——这是 AI 自己的通道，不属于管理面 |

原则：**能由配置文件 + DB 决定的管理操作，Flask 自己做，写完通知桥接重载**；只有内存状态才走 control-api。

### 2.2 安全模型

- Flask：`POST /auth/login` 校验密码（PBKDF2）→ 下发 JWT（HttpOnly + SameSite=Lax，8h）。
- 所有写操作走 `POST/DELETE` + CSRF token（同源 header 校验 + token 双提交）。
- 登录限流 + IP 白名单（沿用现有 `allowedIps` 思路，改为 Flask 中间件）。
- 桥接 control-api：`x-control-token` 常量时间比较 + 只绑定 `127.0.0.1` + 只接受来自 Flask 的 Host。

### 2.3 群聊 / 私聊分离

- `kind === 'private'`：
  - 收到消息**立即**交付（`batchWindowMs = 0`，不进合批队列）；
  - 不排「主动机会检查」、不进潜水定时器、不设 `pendingWake`；
  - 私聊不做 `probability` 抽取（有人说话就回，除非 `paused`）。
- 管理员私聊（`ownerQQ`）：额外挂 `qq_admin_config` 工具：
  - `action: get|set|reload`；`set` 只接受白名单字段（`socialV2.*`、`periods`、`wake.*`、发送限频、工具开关…）；
  - 写 `config.toml`（定向改写，尽量保留注释）→ 调 `reloadConfig()`；
  - 不可热更字段返回 `requiresRestart: true` + 原因。

### 2.4 峰谷策略（多段）

`config.toml`：

```toml
[[periods]]
name = "peak"
days = ["mon","tue","wed","thu","fri"]
start = "08:30"
end = "00:30"
replyProbability = 0.55
reasoningEffort = "high"
proactive = false
sendMaxPerHour = 60

[[periods]]
name = "off-peak"
start = "00:30"
end = "08:30"
replyProbability = 0.9
reasoningEffort = "low"
proactive = true
```

- 匹配：按 `days` + 时间区间（支持跨零点）；无匹配段则用默认值。
- 生效点：`evaluateWakeTriggerV2`（概率）、`sendWakePromptV2`（reasoningEffort/model）、发送限频、主动检查。
- 热更：Flask 写 TOML → 通知桥接 reload；桥接重算 `effectivePeriod()`（每 60s 或消息到达时）。
- 页面：`/periods` 表格增删改 + 时间线预览 + "当前生效段"标识。

### 2.5 配置迁移（P0 已完成的部分）

- `config.toml` 唯一权威；`config.json` 是**过渡期生成的镜像**（gitignore），供未迁移脚本读取。
- `src/config-store.js`：`loadConfigDocument / readConfigRaw / writeConfigDocument / syncConfigMirror / setConfigRoot`。
- 迁移：`node scripts/migrate-config.mjs`（备份 → 写 TOML → 校验往返 → 原 JSON 改名 `.migrated`）。
- **P6 收尾**：删除镜像生成与 `.json` 兜底，清理 40+ 脚本里的 `config.json` 直读。

## 3. 阶段与验收

| 阶段 | 内容 | 验收标准 | 状态 |
| --- | --- | --- | --- |
| P0 | TOML 存储 + 迁移脚本 + 桥接/MCP/核心模块切换 + 镜像同步 + 单测 | 桥接从 `config.toml` 启动；控制台改设置写回 TOML；`test-config-store` 通过 | ✅ 完成（脚本直读待 P6） |
| P1 | Flask 骨架：应用工厂、JWT、CSRF、用户表、登录页、控制面 | 能登录、能看桥接状态、未登录 401、CSRF 生效 | ✅（`web/selftest.py` 13 项） |
| P2 | 控制面 + Flask 页面：会话/工具/日志/峰谷/KB/黑话/用户/修订/人格/预设/令牌/表情 | 旧控制台功能全覆盖 | ✅（12 个页面全部上线） |
| P3 | 知识库 + 黑话 + 表情库并入；`E:\qq-kb-admin` 下线 | 原有 KB 页面功能等价，DB 不变 | ✅（KB/黑话/用户/修订/注入预览；kb-admin 已停用，目录留作备份） |
| P4 | 峰谷多段策略：配置模型 + 桥接生效点 + 页面 | 改时段后无需重启，下一轮唤醒即生效 | ✅（`src/periods.js` + 5 个生效点 + `/periods` 页面） |
| P5 | 私聊即时回复 + 管理员 `qq_admin_config` + `reloadConfig()` | 私聊不再排期；改字段即时生效；越权字段拒绝 | ✅（私聊即时/无主动检查；admin-config 端点 + MCP 工具；5 项回归） |
| P6 | 删 `console.html`、删 JSON 镜像、更新 40+ 脚本、重写 README/部署文档、全量回归 | `npm test` 全绿；文档可从零部署 | ⬜ |

## 3.1 当前约束\n\n> **用户要求：整体重构完成前不启动任何服务。** 所有验证走离线方式（Node 单测、Flask `test_client`、`tomllib` 校验），最终一次性启动验收。\n\n## 4. 风险与对策

| 风险 | 对策 |
| --- | --- |
| 99 个管理端点重写回归风险 | 按页面分批迁移；每批先读旧实现再写新实现；保留 `test-console-ui` 契约测试 |
| TOML 序列化丢注释 | Flask 侧写配置用**定向文本改写**（只替换目标键的行）而非全量序列化；桥接自动写回（token 自愈）时才全量重写并在日志提示 |
| 热重载引发状态不一致 | 只热更白名单字段；定时器/工具面变更标注"需重启" |
| 迁移期间 QQ 掉线 | 新 Flask 与桥接并行；桥接控制台仍可用，验证后再删 `console.html` |
| 用户手改 TOML 语法错误 | 启动即报错并指出行号；Flask 保存前先 `tomllib` 校验，失败不落盘 |

## 5. 文件 TODO 清单

- [ ] `src/control-api.js`（新）
- [ ] `web/app.py`、`web/{config,control,db,auth}.py`、`web/views/*`、`web/templates/*`、`web/static/*`
- [ ] `src/reload-config.js`（热重载白名单）
- [ ] `src/periods.js`（时段匹配 + 覆盖计算，纯函数，可单测）
- [ ] `scripts/test-periods.mjs`、`scripts/test-reload.mjs`
- [ ] 删除 `public/console.html` 与桥接里的 99 个 `/api/*` 管理端点（P6）
- [ ] 迁移 `E:\qq-kb-admin` 的模板/路由到 `web/views/{kb,slang}.py`
- [ ] README / `docs/guides/DEPLOY.md` / `docs/guides/CONFIG.md`
