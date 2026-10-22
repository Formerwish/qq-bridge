# qq-bridge

把 DeepSeek Harness（DSH）驱动的 AI 接入 QQ 群聊与私聊：接收消息、按唤醒策略决定是否回复、通过工具收发消息、使用收藏表情与语音，并附带一个浏览器管理控制台。

## 能力

- **群聊/私聊接入**：通过 SnowLuma（OneBot v11）收发消息，支持引用、@、图片、合并转发、拍一拍。
- **仿真模式**：AI 的文本不自动转发，所有发言通过 `qq_*` 工具完成；可配置唤醒条件、潜水、合批、主动开话题。
- **峰谷策略**：按时间段覆盖回复概率、推理强度、模型、主动检查、发送频率与估算价格。
- **工具开关**：控制台按功能分组启停每个工具；关闭后桥接立即拒绝。
- **收藏表情**：表情库、备注/标签、常用标记、自动补图（概率 + 冷却）、动图抽帧。
- **语音**：从语音库发送语音条，可配置时长/频率上限。
- **知识库与黑话**：第五人格资料按关键词注入，群聊黑话可查询/提交候选/审核。
- **管理控制台**：会话、唤醒、峰谷、工具、表情、知识库、黑话、角色、预设、令牌、用户、配置、日志、用量。
- **管理员能力**：私聊或群内 @ 后可改群名片/资料卡、查用量、读写配置、加白名单。

## 架构

```
QQ  ←→  SnowLuma（OneBot v11）
              │
              ▼
        Node 桥接（src/）
         ├─ /api/...       面向 AI 的 qq_* 工具
         └─ /internal/...  面向控制台
              │
              ▼
        DSH（DeepSeek Harness）── AI 会话与工具调用
              ▲
              │
        Flask 控制台（web/）── 浏览器入口
              │
              ▼
        MySQL（知识库 / 黑话 / 用户）
```

- 桥接负责消息接入、唤醒判定、发送、注入、表情/语音，只监听回环地址。
- 控制台是唯一的浏览器入口，使用登录会话与 CSRF 防护。
- AI 通过 MCP 工具（`qq_*`）操作 QQ；控制台不参与这条链路。

## 工作模式

| 模式 | 行为 |
| --- | --- |
| `reserved2`（默认，仿真） | 文本不自动转发，AI 用工具自主收发；支持唤醒调度、潜水、合批 |
| `chat` | 文本自动转发到 QQ，适合纯聊天 |
| `reserved` | 文本自动转发，保留部分仿真行为 |
| `closed-agent` | 管理员私聊场景，无会话令牌，可使用配置类工具 |

模式在桥接配置中设置；`chat`/`reserved`/`reserved2` 的会话必须挂 `qq-chat-v2` 预设，否则桥接拒绝建会话。

## 目录

```
src/            Node 桥接（bridge.js、config-store.js、periods.js、sticker-lib.js、kb-mysql.js 等）
web/            Flask 控制台（app.py、views/、templates/、static/、management/）
dsh/            DSH 预设（qq-chat-v2）
plugins/        DSH bundle（qq-agent-presets）
roles/          角色卡
scripts/        测试、探针、安装与运维脚本
docs/           文档
state/          运行时数据（gitignore）
config.toml     权威配置（gitignore；模板 config.example.toml）
```

## 快速开始

```powershell
npm install
python -m venv web\.venv
web\.venv\Scripts\python -m pip install -r web\requirements.txt
copy config.example.toml config.toml   # 填写 ownerQQ / allow / consoleToken / kb.mysql
node scripts\setup-dsh.mjs             # 安装 DSH 预设与 MCP
start-all.bat                         # 启动桥接 + 控制台
```

浏览器打开 `http://127.0.0.1:21001/` 登录。

完整步骤见 **[部署文档](docs/DEPLOY.md)**，日常操作见 **[使用文档](docs/USAGE.md)**。

## 配置

`config.toml` 是唯一权威配置。主要段落：

| 段 | 说明 |
| --- | --- |
| `ownerQQ` / `[allow]` / `[deny]` | 管理员与白/黑名单 |
| `[dsh]` | DSH 地址、模型、推理强度、认证 |
| `[snowluma]` | OneBot 网关地址与令牌 |
| `[socialV2]` | 仿真模式、工具开关、唤醒、发送、等待、表情、语音、主动话题 |
| `[[periods]]` | 峰谷时段覆盖（概率/强度/模型/发送上限/价格） |
| `[kb]` / `[slang]` | 知识库与黑话 |
| `[webSearch]` | 联网搜索 |
| `[web]` | 控制台监听与会话时长 |
| `[pricing.models.*]` | 自定义模型价格（元/百万 token） |

控制台"配置"页按功能分组展示全部字段，可热更与需重启分别标记。

## 安全

- 桥接管理接口只监听回环；浏览器只访问控制台。
- 控制台登录使用 HttpOnly 会话 Cookie + CSRF 校验，登录失败有验证码与限流。
- 白名单之外的消息不处理；管理工具仅管理员私聊或群内 @ 后短时间可用。
- 控制台密码为明文存储，仅建议本机单人使用；不要将数据库或控制台暴露到公网。

## 文档

- [部署文档](docs/DEPLOY.md)：依赖、配置、DSH 安装、数据库、启动、升级、排障。
- [使用文档](docs/USAGE.md)：页面说明、用量、配置修改、工具开关、QQ 内操作。
- [知识库说明](docs/guides/KNOWLEDGE_BASE.md)：知识库/黑话表结构与注入规则。

## 测试

```powershell
npm run test:audit
npm run verify:adaptation
web\.venv\Scripts\python web\selftest.py
```

## 许可

MIT
