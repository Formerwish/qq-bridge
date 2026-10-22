# 部署文档

本文说明如何在一台 Windows 机器（也适用于 Linux，命令自行替换）上从零部署 qq-bridge：桥接、控制台、DSH 预设与 MCP 工具、MySQL 知识库，以及升级/备份/排障。

## 1. 组件与端口

| 组件 | 作用 | 默认地址 |
| --- | --- | --- |
| SnowLuma | OneBot v11 网关，连接 QQ | WS `127.0.0.1:3001` / HTTP `127.0.0.1:3000` |
| DSH | DeepSeek Harness，运行 AI 会话 | `127.0.0.1:3080` |
| 桥接 `src/bridge.js` | 消息接入、唤醒、发送、注入、表情/语音 | 仅回环 `127.0.0.1:3100` |
| 控制台 `web/` | 浏览器管理界面（登录/JWT） | `127.0.0.1:21001` |
| MySQL | 知识库、黑话、控制台用户 | `127.0.0.1:10708`，库名 `qq_bridge_kb` |

桥接的 `3100` 只监听回环，不要暴露到公网；浏览器只访问控制台 `21001`。

## 2. 前置依赖

- Windows 10/11（或 Linux）
- Node.js ≥ 22.13（仓库用 ESM，`node -v` 确认）
- Python 3.12
- MySQL 8（本地或内网）
- SnowLuma（OneBot 网关，已登录目标 QQ 号）
- DSH（DeepSeek Harness），并已能正常开一个会话

## 3. 安装

```powershell
cd E:\qq-bridge

# Node 依赖
npm install

# Python 虚拟环境 + 控制台依赖
python -m venv web\.venv
web\.venv\Scripts\python -m pip install -r web\requirements.txt
```

## 4. 配置文件

复制模板并填写：

```powershell
copy config.example.toml config.toml
notepad config.toml
```

`config.toml` 是唯一权威配置（旧 JSON 配置可用 `node scripts/migrate-config.mjs` 迁移，自动备份并校验）。

至少需要填写：

| 配置 | 说明 |
| --- | --- |
| `ownerQQ` | 管理员 QQ 号；私聊命令、群内 @ 管理操作都靠它识别 |
| `allow.private` / `allow.groups` | 允许的私聊 QQ / 群号；为空时按 `allowAllWhenEmpty` 决定是否全放行 |
| `consoleToken` | 桥接与管理端共享的令牌；留空时桥接启动会生成并写回 |
| `dsh.baseUrl` / `dsh.authToken` | DSH 地址与认证；DSH 进程令牌每次启动会变，按实际填写或用控制台"设置"页同步 |
| `kb.mysql.*` | MySQL 连接（库名 `qq_bridge_kb`、只读账号建议） |
| `snowluma.wsUrl` / `httpUrl` | OneBot 网关地址 |

常用配置段：

- `[dsh]`：模型、推理强度、认证头
- `[socialV2]`：仿真模式总开关、预设、初始提示词
- `[socialV2.tools]`：各 `qq_*` 工具开关（控制台"工具"页可视化）
- `[socialV2.wake]` / `[socialV2.send]` / `[socialV2.wait]`：唤醒、发送节奏、等待
- `[socialV2.sticker]`：表情库、自动补图概率（0~1 小数）
- `[[periods]]`：峰谷时段覆盖（回复概率、推理强度、发送上限、价格）
- `[kb]` / `[slang]`：知识库与黑话开关、注入参数
- `[pricing.models.*]`：自定义模型价格（元/百万 token）

保存后可在控制台"配置"页按分组查看与修改；标"可热更"的保存即生效，标"需重启"的要重启桥接。

## 5. DSH 端安装（预设与 MCP）

仓库自带安装脚本，幂等，可重复运行：

```powershell
node scripts\setup-dsh.mjs
```

脚本会：

1. 把 `qq-chat-v2` 预设写入 DSH profile；
2. 在 `cordis.patch.yml` 挂载三个 MCP：
   - `mcp-snowluma`（`src/mcp-snowluma-safe.js`）
   - `mcp-snowluma-host`（`src/mcp-host-server.js`）
   - `mcp-web-search-safe`（`src/mcp-web-search-safe.js`）
3. 注册 `qq-agent-presets` / `qq-mode-console` bundle 并修复失效链接；
4. 修改前备份为 `cordis.patch.yml.qq-bridge.bak`。

安装完成后**重启 DSH**，新建会话时应能看到 `qq-chat-v2` 预设和 `mcp__snowluma__*` 工具。

> 移动或重新 clone 仓库后，需要重新运行一次脚本，否则 DSH 里的绝对路径会失效。

## 6. 数据库

知识库/黑话/用户表由 `web/management/` 下的脚本初始化：

```powershell
cd web
.venv\Scripts\python management\migrate.py    # 建表
.venv\Scripts\python management\seed.py       # 初始数据（可选）
.venv\Scripts\python management\import_slang.py
```

初始管理员在 `kb_user` 表；也可登录后到"用户"页新增。密码为明文存储（见安全说明），仅建议本机单人使用。

## 7. 启动

推荐一键启动：

```powershell
start-all.bat
```

- 桥接窗口：`start.bat` 守护，异常退出 5 秒后自动重启；
- 控制台窗口：`web\run.bat`，异常退出 3 秒后自动重启；
- 已在运行（端口被监听）的组件会跳过。

也可以分别启动：

```powershell
node src\bridge.js        # 桥接
web\run.bat               # 控制台
```

浏览器打开 `http://127.0.0.1:21001/`，用管理员账号登录。

## 8. 验证

```powershell
# 桥接健康
curl http://127.0.0.1:3100/api/status

# 控制台页面（登录后）
# 概览、会话、峰谷、知识库、表情、工具、配置等页面应正常渲染

# 离线自检
npm run verify:adaptation
web\.venv\Scripts\python web\selftest.py
```

桥接日志：`state\bridge.log`；控制台日志：`state\web-console.log` 和控制台窗口。

## 9. 升级与备份

```powershell
git pull
npm install
web\.venv\Scripts\python -m pip install -r web\requirements.txt
# 重启桥接与控制台
```

备份需要保留：

- `config.toml`（配置，含密钥）
- `state\`（会话、表情库、账本、令牌、日志）
- MySQL `qq_bridge_kb`（知识库/黑话/用户）

`state\` 已在 `.gitignore` 中，不会被提交。

## 10. 开机自启（可选）

用任务计划程序创建两个任务：

- 触发：登录时 / 开机时
- 操作：`E:\qq-bridge\start-all.bat`（工作目录 `E:\qq-bridge`）

或把 `start-all.bat` 放进启动文件夹（`shell:startup`）。

## 11. 安全基线

- 控制台只监听回环；如需局域网访问，改 `web.bind` 并配置 `consoleAllowedHosts`；
- `consoleToken`、`dsh.authToken`、MySQL 密码不要提交到仓库；
- 白名单之外的消息默认不处理；
- 管理操作（改群名片/资料卡/配置/查用量）仅管理员私聊或群内 @ 后短时间有效；
- 控制台密码明文存储，数据库不要对外开放。

## 12. 常见问题

| 现象 | 排查 |
| --- | --- |
| 控制台打不开 | 看控制台窗口是否在跑；`netstat -ano | findstr :21001` |
| 桥接 3100 不通 | 看 `state\bridge.log`；DSH/SnowLuma 是否在线 |
| AI 不回消息 | 先看桥接日志是否收到消息/唤醒；再确认 DSH 会话是否卡住，可在"会话"页重置 |
| MCP 工具没出现 | 重新跑 `node scripts\setup-dsh.mjs` 并重启 DSH |
| 知识库不生效 | 检查 `kb.mysql` 连接与 `kb.enabled`；"知识库"页应能搜到条目 |
| 改配置保存失败 | 看控制台提示与 `state\bridge.log`；敏感项需要重启 |
| 端口被占用 | 改 `web.port`（需重启）或先停掉占用进程 |
