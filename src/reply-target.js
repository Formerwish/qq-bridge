// 引用目标判定：模型给的 replyToMessageId，是不是**这一轮它真见过的消息**。
//
// 背景（实测）：唤醒快照是 partial 的（默认只放 12 条未读）。模型有时不去读剩下的，
// 却凭上下文记忆填一个**更早的消息 id** 去引用 —— 结果引到了群里另一个人的无关消息，
// 用户看到的就是「回复错人」。桥接侧无法猜它想回谁，但可以判断"这条它这轮根本没看到"，
// 于是丢掉引用段、文字照发，并在工具结果里说明原因。
//
// 判定口径：命中任意一条即算"见过"——
//   1) 本轮快照 / 读消息工具返回的 messageId 或 seq（由调用方维护的 Set）；
//   2) 当前未读缓冲里的任意一条（模型可能刚拉过列表）；
//   3) 最近 10 条历史消息（含机器人自己刚发的）。
// 其余一律视为"没见过"。

export const RECENT_TAIL = 10;

export function looksUnseen(seenRefs, st, ref) {
  const r = String(ref ?? '').trim();
  if (!r) return false;
  if (seenRefs && typeof seenRefs.has === 'function' && seenRefs.has(r)) return false;
  const pool = [
    ...(Array.isArray(st?.unread) ? st.unread : []),
    ...(Array.isArray(st?.recentMessages) ? st.recentMessages.slice(-RECENT_TAIL) : [])
  ];
  return !pool.some((m) => m && (String(m.messageId ?? '') === r || String(m.seq ?? '') === r));
}

/** 把一批消息里的 messageId / seq 记进"本轮见过"的集合。 */
export function noteSeenRefs(seenMap, key, messages) {
  if (!key || !Array.isArray(messages) || !messages.length) return;
  const now = Date.now();
  let map = seenMap.get(key);
  if (!map) { map = new Map(); seenMap.set(key, map); }
  for (const m of messages) {
    if (!m) continue;
    const mid = m.messageId === undefined || m.messageId === null ? '' : String(m.messageId).trim();
    if (mid) map.set(mid, now);
    if (Number.isSafeInteger(m.seq) && m.seq > 0) map.set(String(m.seq), now);
  }
  if (map.size > 400) {
    // Map 本身是插入序：直接保留最近写入的 200 个（按时间戳排序会在同一毫秒写入时乱序）。
    seenMap.set(key, new Map([...map.entries()].slice(-200)));
  }
}
