# 部署指南（重构版）

零基础从空机器到"QQ 群里能聊天 + 浏览器能管理"。全程 HTTP，不需要自签证书。

## 1. 前置软件

| 组件 | 版本 | 用途 |
| --- | --- | --- |
| Node.js | ≥ 22（推荐 24） | 桥接 / MCP / 脚本 |
| Python | 3.12 | Flask 控制台 |
| MySQL | 8.x | 知识库 / 黑话 / 用户 |
| SnowLuma | 与桥接匹配的版本 | OneBot 网关（QQ ↔ WS） |
| DeepSeek Harness (DSH) | 0.2.0+ | 模型会话与工具宿主 |

## 2. 安装

```powershell
cd E:\qq-bridge
npm install
python -m venv web\.venv
web\.venv\Scripts\python -m pip install -r web\requirements.txt
```

## 3. 数据库

```sql
CREATE DATABASE qq_bridge_kb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'qqkb'@'127.0.0.1' IDENTIFIED BY '强密码';
GRANT ALL PRIVILEGES ON qq_bridge_kb.* TO 'qqkb'@'127.0.0.1';
FLUSH PRIVILEGES;
```

建表：本仓库沿用旧 kb-admin 的 5 张表（`kb_entry` / `kb_user` / `kb_revision` / `kb_slang` / `kb_slang_revision`）。
若从旧库迁移，直接导入旧库即可；新环境可运行原有 `migrate.py`（在旧 kb-admin 项目里，或参考 `docs/guides/KNOWLEDGE_BASE.md` 的 DDL）。

## 4. 配置

```powershell
copy config.example.toml config.toml
notepad config.toml
```

最少需要：

```toml
ownerQQ = 你的QQ号
consoleToken = "随机长令牌"          # 桥接控制面令牌，浏览器看不到
[allow]
private = ["你的QQ号"]
groups = [群号]
[web]
bind = "0.0.0.0"
port = 21001
bridgeUrl = "http://127.0.0.1:3100"
[kb.mysql]
host = "127.0.0.1"
port = 3306
user = "qqkb"
password = "强密码"
database = "qq_bridge_kb"
```

已有 JSON 配置：`node scripts/migrate-config.mjs`（备份 → TOML → 校验；原文件改名 `.migrated`）。

## 5. 启动

三个进程（顺序不严格，但建议先 MySQL，再 SnowLuma，再 DSH，最后桥接/控制台）：

```powershell
# 一键启动（推荐）：桥接 + Flask 控制台，已在跑的自动跳过
start-all.bat（桥接开窗口；控制台无窗口，日志写 state\web-console.log）

# 也可以分开启动：
#   start.bat                     桥接（循环守护）
#   web\run.bat                   控制台（前台看日志；退出后窗口自动关闭）
#   web\start-background.bat      控制台（后台，日志写 state\web-console.log）
```

- 桥接日志：`state/bridge.log`
- 控制台：`http://<机器IP>:21001/`，账号来自 `kb_user`
- 桥接控制台（仅本机，调试用）：`http://127.0.0.1:3100/`（会跳转到 21001）

首次登录：若 `kb_user` 为空，用旧 kb-admin 的 `migrate.py --admin-password <密码>` 建管理员，或在控制台"用户"页由已有管理员创建。

## 6. 开机自启（Windows）

用"任务计划程序"建两个任务（触发器：登录时/开机时）：

| 任务 | 程序 | 参数 | 起始于 |
| --- | --- | --- | --- |
| qq-bridge | `cmd.exe` | `/c "E:\qq-bridge\start.bat"` | `E:\qq-bridge` |
| qq-console | `cmd.exe` | `/c "E:\qq-bridge\web\start-background.bat"` | `E:\qq-bridge\web` |

勾选"不管用户是否登录都运行"时需要把任务设为"使用最高权限运行"（否则读不到桌面会话）。

## 7. 远程访问（纯 HTTP）

- 最快：SSH 隧道 `ssh -L 21001:127.0.0.1:21001 user@host`，本地浏览器开 `http://127.0.0.1:21001`。
- 或：`[web] allowedIps` 限定来源 IP + 防火墙只放行该网段。
- 不要用自签 HTTPS：浏览器会拦截；需要 TLS 就套在反向代理（Nginx/Caddy）上，由反代终结证书。

## 8. 备份与恢复

| 内容 | 位置 | 建议 |
| --- | --- | --- |
| 配置 | `config.toml` | 每日备份（含密钥，注意权限） |
| 运行状态 | `state/`（会话、表情库、日志） | 每周备份；恢复时保持一致 |
| 数据库 | `qq_bridge_kb` | `mysqldump` 每日 |
| 人格卡 | `roles/*.md` | 随仓库管理 |

## 9. 常见问题

| 现象 | 排查 |
| --- | --- |
| 控制台 401/跳登录 | Cookie 被清；重新登录。JWT 密钥在 `state/web-secret`，删除会强制所有人重登 |
| 桥接起不来 | 看 `state/bridge.log`；常见是 3100 被占、config.toml 语法错误（启动会报行号） |
| 知识库改动不生效 | 桥接每 60s 刷新一次 KB 缓存，等下一条唤醒；控制台保存会提示 |
| 峰谷没生效 | 确认 `[[periods]]` 的时间覆盖当前时刻；`/periods` 页顶部会显示"当前生效段"。当前配置按 DeepSeek 定价：工作日 09-12、14-18 为高峰，其余为空闲 |
| 私聊还是隔很久才回 | 确认已升级到本重构版（私聊合批窗口应为 0ms）；检查是否 `paused` |
| 管理员配置工具被拒 | 只允许 `ownerQQ` 的私聊；群聊/他人私聊会 403 |
| MCP 工具没出现 | 关闭工具后需重启 DSH 才完全生效（桥接端已即时 403） |

## 10. 从旧版迁移清单

1. `config.json` → `node scripts/migrate-config.mjs`
2. 停旧 `qq-kb-admin` 进程（已被 `web/` 取代）
3. 启动 `web\run.bat`，用原 `kb_user` 账号登录
4. 旧控制台不再提供；`public/console.html` 仅供历史测试，可忽略
5. 逐步把脚本里的 `config.json` 直读改为 `src/config-store.js`（过渡期 JSON 镜像仍会自动生成）

安全提醒：`config.toml` 与 `state/` 含 token/密码，务必排除在 git 与公开备份之外（仓库 `.gitignore` 已处理）。
