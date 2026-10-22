// 峰谷时段（periods）：按时间给"回复概率 / 推理强度 / 模型 / 主动检查 / 发送限频"做覆盖。
//
// 设计：
// - 纯函数，不读配置、不看时钟（时间由调用方传入），方便单测与预览。
// - 任意多段：`[[periods]]` 数组，每段 `start`/`end` 用 "HH:MM"，**支持跨零点**
//   （如 22:00 → 06:00）；`days` 可限定星期（缺省=每天）。
// - 命中多段时**取第一段**（顺序即优先级），便于"先特殊后一般"。
// - 没有命中段 → 空对象，调用方回退到全局默认值。
//
// 覆盖字段（全部可选）：
//   replyProbability  0~1     普通消息唤醒概率（覆盖 wakeConfig.triggers.probability）
//   reasoningEffort   low/medium/high/max
//   model             string
//   proactive         bool     是否允许"主动找话题"检查
//   sendMaxPerMinute  int
//   sendMaxPerHour    int

export const DAY_KEYS = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'];
export const REASONING_EFFORTS = ['low', 'medium', 'high', 'max'];

const DAY_ALIASES = {
  sun: 'sun', sunday: 'sun', 日: 'sun', 周日: 'sun', 周天: 'sun',
  mon: 'mon', monday: 'mon', 一: 'mon', 周一: 'mon',
  tue: 'tue', tuesday: 'tue', 二: 'tue', 周二: 'tue',
  wed: 'wed', wednesday: 'wed', 三: 'wed', 周三: 'wed',
  thu: 'thu', thursday: 'thu', 四: 'thu', 周四: 'thu',
  fri: 'fri', friday: 'fri', 五: 'fri', 周五: 'fri',
  sat: 'sat', saturday: 'sat', 六: 'sat', 周六: 'sat'
};

/** "HH:MM" → 当天分钟数；非法返回 null。 */
export function parseHM(value) {
  const match = /^(\d{1,2}):(\d{2})$/.exec(String(value ?? '').trim());
  if (!match) return null;
  const hour = Number(match[1]);
  const minute = Number(match[2]);
  if (hour > 23 || minute > 59) return null;
  return hour * 60 + minute;
}

export function formatHM(minutes) {
  const value = Math.max(0, Math.min(24 * 60 - 1, Math.round(Number(minutes) || 0)));
  return `${String(Math.floor(value / 60)).padStart(2, '0')}:${String(value % 60).padStart(2, '0')}`;
}

/** 星期归一：接受 mon/Monday/周一/数字 0-6（0=周日）。 */
export function normalizeDays(raw) {
  if (!Array.isArray(raw) || raw.length === 0) return null;
  const out = new Set();
  for (const item of raw) {
    const text = String(item ?? '').trim().toLowerCase();
    if (!text) continue;
    if (/^[0-6]$/.test(text)) { out.add(DAY_KEYS[Number(text)]); continue; }
    const mapped = DAY_ALIASES[text];
    if (mapped) out.add(mapped);
  }
  return out.size ? [...out] : null;
}

function normalizeNumber(value, min, max) {
  const num = Number(value);
  if (!Number.isFinite(num)) return null;
  return Math.min(max, Math.max(min, num));
}

/** 配置数组 → 规范化后的时段列表（非法项直接丢弃，避免一条坏配置带走全部策略）。 */
export function normalizePeriods(raw) {
  if (!Array.isArray(raw)) return [];
  return raw
    .map((item, index) => {
      const start = String(item?.start ?? '').trim();
      const end = String(item?.end ?? '').trim();
      const startMin = parseHM(start);
      const endMin = parseHM(end);
      if (startMin === null || endMin === null || startMin === endMin) return null;
      const effort = String(item?.reasoningEffort ?? '').trim().toLowerCase();
      return {
        name: String(item?.name ?? '').trim() || `时段${index + 1}`,
        start: formatHM(startMin),
        end: formatHM(endMin),
        days: normalizeDays(item?.days),
        replyProbability: normalizeNumber(item?.replyProbability, 0, 1),
        reasoningEffort: REASONING_EFFORTS.includes(effort) ? effort : null,
        model: typeof item?.model === 'string' && item.model.trim() ? item.model.trim() : null,
        proactive: typeof item?.proactive === 'boolean' ? item.proactive : null,
        sendMaxPerMinute: Number.isFinite(Number(item?.sendMaxPerMinute)) && Number(item.sendMaxPerMinute) > 0
          ? Math.round(Number(item.sendMaxPerMinute)) : null,
        sendMaxPerHour: Number.isFinite(Number(item?.sendMaxPerHour)) && Number(item.sendMaxPerHour) > 0
          ? Math.round(Number(item.sendMaxPerHour)) : null
      };
    })
    .filter(Boolean);
}

function dayKey(date, offsetDays = 0) {
  const copy = new Date(date.getTime());
  copy.setDate(copy.getDate() + offsetDays);
  return DAY_KEYS[copy.getDay()];
}

/** 某一时刻是否落在该时段内（处理跨零点与 days 的"归属开始日"语义）。 */
export function isInPeriod(period, date = new Date()) {
  const start = parseHM(period.start);
  const end = parseHM(period.end);
  if (start === null || end === null) return false;
  const minutes = date.getHours() * 60 + date.getMinutes();
  const crossMidnight = start > end;
  if (crossMidnight) {
    if (minutes >= start) return !period.days || period.days.includes(dayKey(date));
    if (minutes < end) return !period.days || period.days.includes(dayKey(date, -1));
    return false;
  }
  if (minutes < start || minutes >= end) return false;
  return !period.days || period.days.includes(dayKey(date));
}

/** 返回当前命中的时段（第一段优先）或 null。 */
export function periodAt(periods, date = new Date()) {
  const list = Array.isArray(periods) ? periods : [];
  for (const period of list) {
    if (isInPeriod(period, date)) return period;
  }
  return null;
}

/** 当前生效的覆盖值（只含该时段显式配置的字段）。 */
export function overridesAt(periods, date = new Date()) {
  const period = periodAt(periods, date);
  if (!period) return {};
  const out = {};
  for (const key of ['replyProbability', 'reasoningEffort', 'model', 'proactive', 'sendMaxPerMinute', 'sendMaxPerHour']) {
    if (period[key] !== null && period[key] !== undefined) out[key] = period[key];
  }
  return out;
}

/** 给控制台用的摘要（当前段 + 下一段切换时间）。 */
export function describePeriods(periods, date = new Date()) {
  const period = periodAt(periods, date);
  return {
    now: date.toISOString(),
    current: period ? period.name : null,
    overrides: overridesAt(periods, date),
    total: Array.isArray(periods) ? periods.length : 0
  };
}
