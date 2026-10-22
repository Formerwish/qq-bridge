// 峰谷时段单测（纯函数，不需要服务）。
// 运行：node scripts/test-periods.mjs

import assert from 'node:assert/strict';
import {
  parseHM, formatHM, normalizeDays, normalizePeriods, isInPeriod, periodAt, overridesAt, describePeriods
} from '../src/periods.js';

let passed = 0;
function test(name, fn) {
  try { fn(); passed++; console.log(`  ✓ ${name}`); }
  catch (e) { console.error(`  ✗ ${name}\n    ${e?.message ?? e}`); process.exitCode = 1; }
}

const at = (day, hour, minute = 0) => {
  const date = new Date(2026, 9, 19, hour, minute, 0); // 2026-10-19 是周一
  const delta = (day - date.getDay() + 7) % 7; // 0=周日
  date.setDate(date.getDate() + delta);
  return date;
};

console.log('periods 单测：');

test('HH:MM 解析/格式化', () => {
  assert.equal(parseHM('08:30'), 510);
  assert.equal(parseHM('00:00'), 0);
  assert.equal(parseHM('24:00'), null);
  assert.equal(parseHM('8:5'), null);
  assert.equal(formatHM(510), '08:30');
});

test('星期归一（英文/中文/数字）', () => {
  assert.deepEqual(normalizeDays(['mon', '周三', 5]).sort(), ['fri', 'mon', 'wed']);
  assert.equal(normalizeDays([]), null);
});

test('普通时段（非跨零点）', () => {
  const periods = normalizePeriods([{ name: '白天', start: '08:00', end: '18:00', replyProbability: 0.5 }]);
  assert.equal(periodAt(periods, at(1, 12))?.name, '白天');
  assert.equal(periodAt(periods, at(1, 7, 59)), null);
  assert.equal(periodAt(periods, at(1, 18)), null);
});

test('跨零点时段（22:00→06:00）', () => {
  const periods = normalizePeriods([{ name: '夜间', start: '22:00', end: '06:00' }]);
  assert.equal(periodAt(periods, at(1, 23))?.name, '夜间');
  assert.equal(periodAt(periods, at(2, 3))?.name, '夜间');
  assert.equal(periodAt(periods, at(2, 7)), null);
});

test('days 归属开始日（跨零点尾部仍算前一天）', () => {
  const periods = normalizePeriods([{ name: '周五夜', start: '22:00', end: '02:00', days: ['fri'] }]);
  // 周五 23:00 → 命中
  assert.equal(periodAt(periods, at(5, 23))?.name, '周五夜');
  // 周六 01:00 → 属于周五夜，命中
  assert.equal(periodAt(periods, at(6, 1))?.name, '周五夜');
  // 周六 23:00 → 不命中（周六不在 days）
  assert.equal(periodAt(periods, at(6, 23)), null);
  // 周日 01:00 也不命中
  assert.equal(periodAt(periods, at(0, 1)), null);
});

test('多段按顺序取第一段命中', () => {
  const periods = normalizePeriods([
    { name: '凌晨', start: '00:00', end: '06:00', reasoningEffort: 'low' },
    { name: '全天兜底', start: '06:00', end: '00:00', reasoningEffort: 'high' }
  ]);
  assert.equal(periodAt(periods, at(1, 3))?.name, '凌晨');
  assert.equal(periodAt(periods, at(1, 12))?.name, '全天兜底');
});

test('overridesAt 只返回显式字段', () => {
  const periods = normalizePeriods([
    { name: '山谷', start: '00:00', end: '08:00', replyProbability: 0.9, proactive: true },
    { name: '峰', start: '08:00', end: '00:00', replyProbability: 0.3, reasoningEffort: 'max' }
  ]);
  assert.deepEqual(overridesAt(periods, at(1, 3)), { replyProbability: 0.9, proactive: true });
  assert.deepEqual(overridesAt(periods, at(1, 12)), { replyProbability: 0.3, reasoningEffort: 'max' });
  assert.deepEqual(overridesAt([], at(1, 3)), {});
});

test('非法配置被丢弃，不连累其它段', () => {
  const periods = normalizePeriods([
    { name: '坏', start: '25:00', end: '06:00' },
    { name: '好', start: '08:00', end: '09:00' }
  ]);
  assert.equal(periods.length, 1);
  assert.equal(periods[0].name, '好');
});

test('describePeriods 摘要', () => {
  const periods = normalizePeriods([{ name: '夜', start: '00:00', end: '06:00', model: 'deepseek-flash' }]);
  const info = describePeriods(periods, at(1, 2));
  assert.equal(info.current, '夜');
  assert.equal(info.overrides.model, 'deepseek-flash');
  assert.equal(info.total, 1);
});

console.log(`\n通过 ${passed} 项。`);
