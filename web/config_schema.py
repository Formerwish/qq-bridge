"""高级配置：把 config.toml 全部字段按用途汉化，能选项就用选择框；已被专用页面覆盖的字段不再重复。"""

from __future__ import annotations

import re

SECTION_LABELS = {
    "dsh": "DSH 连接",
    "role": "角色注入",
    "snowluma": "SnowLuma 网关",
    "pricing": "价目表",
    "security": "安全",
    "slang": "黑话库",
    "kb": "知识库",
    "socialV2": "其它仿真参数",
    "webSearch": "联网搜索",
    "web": "控制台",
    "presets": "预设",
    "voice": "语音",
    "media": "媒体处理",
    "misc": "其它",
}

TOKENS = {
    "enabled": "启用", "auto": "自动", "autoResearch": "自动研究", "autoProbability": "自动补图概率",
    "autoCooldownMs": "自动补图冷却（毫秒）", "autoReplyCheckMs": "自动回复检查间隔（毫秒）",
    "batchWindowMs": "合批窗口（毫秒）", "probability": "概率", "replyProbability": "回复概率",
    "paused": "暂停", "model": "模型", "provider": "提供方", "reasoningEffort": "推理强度",
    "contextWindow": "上下文条数",
    "probability_": "概率", "minMs": "最小间隔（毫秒）", "maxMs": "最大间隔（毫秒）",
    "idle": "空闲",
    "proactive": "主动开话题", "checkIntervalMinMs": "检查最小间隔（毫秒）",
    "checkIntervalMaxMs": "检查最大间隔（毫秒）", "idleThresholdMs": "空闲阈值（毫秒）",
    "maxPerMinute": "每分钟上限", "maxPerHour": "每小时上限", "maxSendPerMinute": "每分钟发送上限",
    "maxSendPerHour": "每小时发送上限", "sendTiming": "发送节奏", "sendDelayMs": "发送间隔（毫秒）",
    "burstEnabled": "连发", "burstMaxMessages": "连发最多条数", "burstIntervalMinMs": "连发最小间隔（毫秒）",
    "burstIntervalMaxMs": "连发最大间隔（毫秒）", "longGapProbability": "长间隔概率",
    "longGapMinMs": "长间隔最小（毫秒）", "longGapMaxMs": "长间隔最大（毫秒）",
    "maxMessageChars": "单条最大字数", "gapBaseMs": "基础间隔（毫秒）", "gapPerCharMs": "每字间隔（毫秒）",
    "maxGapMs": "最大条间隔（毫秒）", "wait": "等待", "defaultMs": "默认等待（毫秒）",
    "maxMs2": "最大等待（毫秒）", "quietMs": "静默窗口（毫秒）", "minQuietAfterNewMs": "新消息后最短静默（毫秒）",
    "sticker": "表情包", "includeInPrompt": "写入提示词", "promptMaxStickers": "提示词最多列表情数",
    "syncTtlMs": "同步缓存（毫秒）", "maxListCount": "列表最多条数", "collect": "偷图",
    "maxRemarkChars": "备注最大长度", "voice": "语音", "maxSeconds": "最长语音（秒）",
    "maxBytes": "最大字节", "dir": "语音目录", "loudness": "响度", "ffmpegPath": "ffmpeg 路径",
    "defaultVolume": "默认音量", "autoReadback": "自动回读", "feedback": "反馈", "maxLength": "最大长度",
    "notifyOwnerOnError": "出错通知管理员", "context": "上下文", "recentLimit": "最近消息条数",
    "unreadLimit": "未读条数", "inlineWakeMessages": "唤醒内联消息", "wakeMessageLimit": "唤醒消息上限",
    "wakeRecentLimit": "唤醒最近条数", "wakeMaxChars": "唤醒最大字符", "media": "媒体", "maxPixels": "最大像素",
    "maxCount": "最多数量", "gif": "GIF", "frames": "帧数", "cellPx": "单格像素", "onlyAnimated": "仅动图",
    "webSearch": "联网搜索", "maxUses": "最多使用次数", "maxResults": "最多结果数", "timeoutMs": "超时（毫秒）",
    "apiKey": "API Key", "baseURL": "接口地址", "maxTokens": "最大 token", "web": "控制台",
    "bind": "监听地址", "port": "端口", "sessionHours": "会话时长（小时）", "loginRate": "登录限流",
    "presets": "预设", "agentPreset": "聊天预设", "learnerPreset": "学习预设", "workspaceTitle": "工作区标题",
    "enabled_": "启用", "maxInjectChars": "人格注入上限（字符）", "ownerQQ": "管理员 QQ",
    "sendDelayMs": "发送间隔（毫秒）", "questionTimeoutMs": "提问超时（毫秒）",
    "extractMinMessages": "抽取最少消息数", "extractCooldownMs": "抽取冷却（毫秒）",
    "inferenceThresholds": "推断阈值", "injectMax": "注入最多条数", "researchSchedule": "定时研究",
    "researchAt": "研究时间", "researchWeekday": "研究星期", "researchMinCandidates": "最少候选数",
    "researchMaxPerRun": "每次最多研究", "mysql": "数据库", "host": "主机", "user": "用户",
    "database": "数据库", "connectionLimit": "连接数", "connectTimeoutMs": "连接超时（毫秒）",
    "inject": "注入", "maxEntries": "最多注入条数", "maxChars": "最多字符", "query": "查询",
    "previewChars": "预览字符", "cacheTtlMs": "缓存（毫秒）", "learn": "学习", "store": "存储",
    "interceptNotify": "拦截通知", "models": "模型", "label": "名称", "off": "优惠价",
    "cacheHit": "缓存命中", "cacheMiss": "缓存未命中", "output": "输出", "silenceWarnMs": "静默告警（毫秒）",
    "followDiscoveredEndpoint": "跟随发现端点", "wsUrl": "长连接地址", "httpUrl": "接口地址",
    "accessToken": "访问令牌", "launcherPath": "启动器路径", "homeDir": "主目录",
    "consoleUrl": "控制台地址", "consoleToken": "控制台令牌", "consoleAllowedHosts": "允许的主机",
    "allowRemote": "允许远程", "authToken": "认证令牌", "authHeader": "认证头", "authPrefix": "认证前缀",
    "baseUrl": "基础地址", "allowAllWhenEmpty": "空白名单全放行", "ackMessage": "确认语",
    "sessionCwd": "会话工作目录", "workspaceTitle_": "工作区标题", "autoReplyCheckMs_": "自动回复检查（毫秒）",
    "provideRecommendations": "提供推荐值", "initialPromptMaxChars": "初始提示词上限（字符）",
    "wake": "唤醒", "send": "发送",
    "preSleepWaitMs": "沉睡前观察（毫秒）",
    "defaultMode": "默认模式", "recommendedDefaultInfinite": "推荐默认无限期",
    "sleepMinMs": "最短潜水（毫秒）", "sleepMaxMs": "最长潜水（毫秒）",
    "recommendedSleepMinMs": "推荐最短潜水（毫秒）", "recommendedSleepMaxMs": "推荐最长潜水（毫秒）",
    "recommendedKeywords": "推荐关键词", "recommendedAtMention": "推荐 @ 唤醒",
    "recommendedNameMention": "推荐名字唤醒", "recommendedQuestion": "推荐提问唤醒",
    "recommendedPoke": "推荐拍一拍唤醒", "recommendedHint": "推荐提示",
    "noActionLimit": "连续无行动上限", "defaultQuietMs": "默认静默窗口（毫秒）",
    "allowAbsolutePath": "允许绝对路径", "bridgeUrl": "桥接地址",

}



# 二级功能分组：把 socialV2 的大卡片拆成按用途的独立卡片。
SUBGROUP_LABELS = {
    "socialV2.sticker": "表情包与自动补图",
    "socialV2.send": "发送节奏与连发",
    "socialV2.wake": "唤醒与潜水",
    "socialV2.wait": "等待与合批",
    "socialV2.context": "上下文与记忆",
    "socialV2.media": "媒体处理",
    "socialV2.voice": "语音",
    "socialV2.feedback": "反馈",
    "socialV2.proactive": "主动开话题",
    "socialV2.safety": "安全与静默",
    "socialV2.usage": "用量",
    "socialV2.slang": "黑话",
    "socialV2.kb": "知识库",
}

# 卡片展示顺序：先聊天主链路，再表情/记忆，再外部集成。
GROUP_ORDER = [
    "socialV2.sticker", "socialV2.send", "socialV2.wake", "socialV2.wait",
    "socialV2.proactive", "socialV2.context", "socialV2.media", "socialV2.voice",
    "socialV2.feedback", "socialV2.safety", "socialV2.slang", "socialV2.kb",
    "socialV2",
    "dsh", "presets", "role",
    "kb", "slang", "webSearch", "voice", "media",
    "web", "security", "pricing", "snowluma", "misc",
]


def group_key(path: str) -> str:
    parts = path.split(".")
    if parts and parts[0] == "socialV2" and len(parts) > 2:
        key = "socialV2." + parts[1]
        if key in SUBGROUP_LABELS:
            return key
    # 顶层零散键（没有对应 section）统一收进「其它」，避免出现一堆单字段卡片
    if len(parts) == 1 and parts[0] not in SECTION_LABELS:
        return "misc"
    return parts[0]


def group_label(key: str) -> str:
    return SUBGROUP_LABELS.get(key) or SECTION_LABELS.get(key) or key

ENUMS = {
    "dsh.provider": ["deepseek-official"],
    "dsh.model": ["deepseek-flash", "deepseek-pro"],
    "dsh.reasoningEffort": ["low", "high", "max"],
    "webSearch.provider": ["auto", "deepseek", "bing"],
    "voice.loudness": ["soft", "normal", "loud"],
    "slang.researchSchedule": ["off", "daily", "weekly"],
    "slang.researchWeekday": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
    "web.bind": ["127.0.0.1", "0.0.0.0"],
}

# 已被专用页面覆盖、这里不再重复展示的前缀
EXCLUDED = (
    "allow.", "deny.", "ownerQQ", "consoleUrl", "consoleToken", "consoleAllowedHosts",
    "web.sessionHours", "periods", "socialV2.tools.", "agentPreset",
)

SECRET_RE = re.compile(r"token|password|apikey|secret", re.I)


def excluded(path: str) -> bool:
    return any(path == x.rstrip(".") or path.startswith(x) for x in EXCLUDED)


def _humanize(key: str) -> str:
    if key in TOKENS:
        return TOKENS[key]
    parts = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", key).replace("_", " ").split()
    out = []
    for p in parts:
        low = p.lower()
        out.append(TOKENS.get(p, TOKENS.get(low, p)))
    return "".join(out) if all("\u4e00" <= c <= "\u9fff" or c.isalnum() for c in "".join(out)) else key


def label_for(path: str) -> str:
    """字段标签只写用途，不重复 section 名（section 已经是卡片标题）。"""
    _, _, rest = path.partition(".")
    if not rest:
        return _humanize(path)
    parts = [p for p in rest.split(".") if p]
    labels = []
    prev = ""
    for part in parts:
        if prev == "models":
            labels.append(part)  # 模型名保留原文，例如 my-relay-model
        else:
            labels.append(_humanize(part))
        prev = part
    return " · ".join(labels)


def flatten(node, prefix="", out=None):
    out = out if out is not None else []
    for key, value in node.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            flatten(value, path, out)
        elif isinstance(value, list) and value and all(isinstance(x, dict) for x in value):
            for i, item in enumerate(value):
                flatten(item, f"{path}[{i}]", out)
        else:
            out.append((path, value))
    return out


def duration_unit(path: str, value) -> str:
    """毫秒字段的展示单位：普通时长用秒，超过 1 小时的用小时。"""
    if not path.endswith("Ms"):
        return ""
    try:
        ms = float(value)
    except (TypeError, ValueError):
        return "秒"
    return "小时" if abs(ms) >= 3600_000 else "秒"


def duration_factor(unit: str) -> int:
    return 3600_000 if unit == "小时" else 1000


def kind_for(path: str) -> str:
    """按路径判断控件类型；与 build_fields 的判定保持一致。"""
    if path.lower().endswith("probability"):
        return "percent"
    if path.endswith("Ms"):
        return "duration"
    if any(part.endswith("_list") for part in path.split(".")) or path.endswith((".keywords", ".speakerIds", ".allow", ".deny")):
        return "list"
    return "auto"


def build_fields(cfg: dict) -> list[dict]:
    fields = []
    for path, value in flatten(cfg):
        if excluded(path) or SECRET_RE.search(path):
            continue
        unit = duration_unit(path, value) if not isinstance(value, bool) else ""
        is_prob = path.lower().endswith("probability") and not isinstance(value, bool)
        if unit:
            kind = "duration"
            try:
                value = round(float(value) / duration_factor(unit), 3)
            except (TypeError, ValueError):
                value = 0
        elif is_prob:
            kind = "percent"
            try:
                value = round(float(value) * 100, 4)
            except (TypeError, ValueError):
                value = 0
        elif isinstance(value, bool):
            kind = "bool"
        elif isinstance(value, (int, float)):
            kind = "number"
        elif isinstance(value, list):
            kind = "list"
        else:
            kind = "text"
        key = group_key(path)
        short_path = path[len(key) + 1:] if key and path.startswith(key + ".") else path
        fields.append({
            "path": path,
            "label": label_for(short_path).replace("（毫秒）", "") + ("（%）" if is_prob else (f"（{unit}）" if unit else "")),
            "kind": kind,
            "value": value,
            "list_text": ", ".join(str(x) for x in value) if kind == "list" else "",
            "options": ENUMS.get(path, []),
            "unit": unit,
        })
    return fields
