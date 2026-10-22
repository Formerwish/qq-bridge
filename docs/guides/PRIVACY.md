# 隐私与数据说明

本项目在本地运行，数据默认只保存在本机。本文说明会接触哪些数据、存放在哪里、以及清理方式。

## 1. 会产生和保存的数据

| 数据 | 位置 | 说明 |
| --- | --- | --- |
| 配置（含令牌、数据库口令） | `config.toml` | 已被 `.gitignore` 排除；不要提交 |
| 会话状态、待处理消息 | `state/social-v2.json` | 含 QQ 号、群号、消息摘要 |
| 令牌用量账本 | `state/token-usage.jsonl` | 每条 turn 的 token 数与模型名，不含消息正文 |
| 表情库 | `state/stickers.json` | 收藏表情 ID、备注、使用次数 |
| 黑话/知识库镜像 | `state/slang.json`、MySQL | 群聊黑话、第五人格资料 |
| 运行日志 | `state/bridge.log`、`state/web-console.log` | 可能包含消息摘要与 QQ 号 |
| 控制台用户 | MySQL 用户表 | 用户名、明文密码（见安全说明） |

`state/`、`config.toml`、`config.json`、迁移备份等均已在 `.gitignore` 中。

## 2. 会发给外部服务的数据

- 消息内容与相关上下文会发给 DSH，再由 DSH 调用配置的模型提供方；
- 知识库检索命中内容、表情描述会进入提示词；
- 联网搜索开启时，搜索词会发给搜索提供方。

不需要这些能力时，可在配置中关闭对应功能（`kb.enabled`、`slang.enabled`、`webSearch`、`socialV2.sticker` 等）。

## 3. 凭据管理

- `consoleToken`、`dsh.authToken`、SnowLuma token、MySQL 口令只保存在 `config.toml` 与运行内存中；
- 控制台不把令牌下发到浏览器；管理员工具调用需要会话令牌或管理员私聊；
- 轮换令牌后重启桥接即可生效；
- 不要把 `config.toml`、`state/`、数据库备份提交到仓库或发给他人。

## 4. 清理数据

```powershell
# 停止桥接与控制台后
Remove-Item state\social-v2.json, state\token-usage.jsonl, state\stickers.json, state\slang.json
Remove-Item state\bridge.log, state\web-console.log
```

知识库/黑话/用户在 MySQL 中，按需删除对应库或表；删除前先备份。

## 5. 公开仓库前的检查

- `git status` 确认没有 `config.toml`、`state/`、`config.json`、迁移备份；
- 搜索真实 QQ 号、群号、本机绝对路径、令牌；
- 需要保留的示例数据改成占位符；
- 历史提交无法通过删除文件清除，若曾提交过敏感信息，应视为已泄露并轮换凭据。
