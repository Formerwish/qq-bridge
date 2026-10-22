"""工具开关页：直接改 config.toml 的 [socialV2.tools]，再让桥接热重载。

设计取舍：
- 关掉某个工具后，桥接端立刻 403；但 MCP 侧的工具注册是启动时决定的，
  所以页面明确提示"完全生效需重启 DSH"。
- 写配置走 config_edit 的定向改写（保留注释），写前 tomllib 校验。
- flag 名必须与 src/mcp-snowluma-safe.js 的 TOOL_CONFIG_FLAGS 完全一致，
  否则页面显示"已关"但 MCP 仍注册/仍放行。
"""

from __future__ import annotations

import config_edit
import control
from flask import Blueprint, flash, redirect, render_template, request, url_for

from views.auth import login_required

bp = Blueprint("tools", __name__)

GROUP_ORDER = [
    ("send", "发送与互动"),
    ("read", "读取与查询"),
    ("sticker", "表情与媒体"),
    ("knowledge", "记忆与知识"),
    ("admin", "管理（仅管理员）"),
]

# (flag, 标题, 工具名, 分组, 说明, 是否仅管理员)
TOOL_DEFS: list[dict] = [
    ("sendMessage", "发送消息", "qq_send_message", "send", "向当前会话发一条文本（支持引用）", False),
    ("sendGroup", "发群消息", "qq_send_group_message", "send", "向白名单群发文本", False),
    ("sendPrivate", "发私聊", "qq_send_private_message", "send", "向白名单好友发文本", False),
    ("reply", "引用回复", "qq_reply", "send", "引用某条消息回复", False),
    ("sendBurst", "连发", "qq_send_burst", "send", "分多条、带真人化间隔发送", False),
    ("sendPoke", "拍一拍", "qq_send_poke", "send", "拍一拍群友/私聊对象", False),
    ("sendVoice", "发语音", "qq_send_voice / qq_list_voices", "send", "发送语音库里的音频（受时长/频率限制）", False),

    ("getUnread", "读未读", "qq_get_unread_messages", "read", "读取未读消息", False),
    ("getRecent", "读最近消息", "qq_get_recent_messages", "read", "读取最近消息历史", False),
    ("getMyRecent", "看自己最近说过的话", "qq_get_my_recent_messages", "read", "回看自己最近发的消息", False),
    ("getMessageDetail", "看消息详情", "qq_get_message_detail", "read", "查单条消息发送者/引用/正文", False),
    ("getImages", "看消息图片", "qq_get_message_images", "read", "把消息里的图片/表情喂给视觉", False),
    ("getForwardMsg", "看合并转发", "qq_get_forward_msg", "read", "展开合并转发内容", False),
    ("getGroupHistory", "看群历史", "qq_get_group_history", "read", "读取群消息历史", False),
    ("getGroupMembers", "看群成员", "qq_get_group_members", "read", "列出群成员", False),
    ("getActiveMembers", "看活跃成员", "qq_get_active_members", "read", "最近活跃的人", False),
    ("getPrompt", "看提示词", "qq_get_prompt", "read", "读角色/推荐值/工具/唤醒配置", False),
    ("socialState", "看社交状态", "qq_social_state", "read", "未读数、上次唤醒原因等", False),
    ("waitMessages", "等待消息", "qq_wait_for_messages", "read", "长轮询等待新消息（私聊已禁用）", False),
    ("markRead", "标记已读", "qq_mark_read", "read", "按水位标记已读", False),
    ("setWakeConfig", "设置唤醒", "qq_set_wake_config", "read", "潜水/活跃/触发条件", False),

    ("sendSticker", "发表情", "qq_send_sticker", "sticker", "发一张收藏表情", False),
    ("listStickers", "表情列表", "qq_list_stickers", "sticker", "查收藏表情与备注", False),
    ("getStickerImage", "看表情图", "qq_get_sticker_image", "sticker", "把表情图片喂给视觉", False),
    ("collectSticker", "收藏表情", "qq_collect_sticker", "sticker", "把别人发的表情收进收藏", False),
    ("stickerNote", "表情备注", "qq_sticker_note", "sticker", "记录本地认知（备注/标签/用法）", False),
    ("setStickerRemark", "改 QQ 表情备注", "qq_set_sticker_remark", "sticker", "改 QQ 账号里的官方备注（默认关闭）", False),

    ("memory", "轻量记忆", "qq_memory_append / query / remove / clear", "knowledge", "记录话题、待说想法、群友印象", False),
    ("feedback", "反馈问题", "qq_report_feedback", "knowledge", "把困惑/异常报给管理端", False),
    ("slangQuery", "黑话查询", "qq_slang_query", "knowledge", "查已确认的群聊黑话", False),
    ("slangSubmit", "提交黑话候选", "qq_slang_submit", "knowledge", "把陌生词交给管理员确认", False),
    ("kbSearch", "知识库检索", "qq_kb_search", "knowledge", "查第五人格角色/皮肤/赛事资料", False),

    ("setGroupCard", "改群名片", "qq_set_group_card", "admin", "修改机器人在当前群的名片", True),
    ("setProfile", "改资料卡/昵称", "qq_set_profile", "admin", "改昵称/个性签名", True),
    ("usage", "用量查询", "qq_usage", "admin", "查 token 用量与估算费用", True),
    ("adminConfig", "管理员配置", "qq_admin_config", "admin", "读写 config.toml（敏感项需重启）", True),
]


def _flags() -> dict:
    try:
        return config_edit.get_path("socialV2.tools", default={}) or {}
    except config_edit.ConfigEditError:
        return {}


def _build_groups(flags: dict) -> list[dict]:
    groups = []
    for key, label in GROUP_ORDER:
        items = []
        for flag, title, tool, group, desc, admin in TOOL_DEFS:
            if group != key:
                continue
            items.append({
                "flag": flag,
                "title": title,
                "tool": tool,
                "desc": desc,
                "admin": admin,
                "on": bool(flags.get(flag, True)),
            })
        groups.append({"key": key, "label": label, "tools": items, "on": sum(1 for x in items if x["on"])})
    return groups


@bp.get("/tools")
@login_required
def index():
    flags = _flags()
    groups = _build_groups(flags)
    total = sum(len(g["tools"]) for g in groups)
    enabled = sum(g["on"] for g in groups)
    return render_template("tools.html", groups=groups, total=total, enabled=enabled)


@bp.post("/tools")
@login_required
def save():
    flags = _flags()
    items = {}
    for flag, _title, _tool, _group, _desc, _admin in TOOL_DEFS:
        checked = request.form.get(flag) == "on"
        if bool(flags.get(flag, True)) != checked:
            items[f"socialV2.tools.{flag}"] = checked
    if not items:
        flash("没有变化", "ok")
        return redirect(url_for("tools.index"))
    try:
        config_edit.set_values(items)
    except config_edit.ConfigEditError as exc:
        flash(f"写入配置失败：{exc}", "error")
        return redirect(url_for("tools.index"))
    hint = "已写入 config.toml"
    try:
        control.reload_config()
        hint += "，桥接已热重载"
    except control.BridgeError as exc:
        hint += f"；桥接未重载（{exc}），下次启动生效"
    flash(f"{hint}。关闭工具对 MCP 完全生效需重启 DSH。", "ok")
    return redirect(url_for("tools.index"))
