// 引用目标判定单测：模型给的 replyToMessageId 是不是「本轮真见过」的消息。
//
// 背景：partial 快照下，模型会凭记忆填旧 id 去引用，结果引到别人发的无关消息
// （用户看到"回复错人"）。桥接兜底规则见 src/reply-target.js。
//
// 运行：node scripts/test-reply-target.mjs

import assert from 'node:assert/strict';
import { looksUnseen, noteSeenRefs, RECENT_TAIL } from '../src/reply-target.js';

let passed = 0;
const test = (name, fn) => {
  try { fn(); passed++; console.log(`  ✓ ${name}`); }
  catch (e) { console.error(`  ✗ ${name}\n    ${e?.message ?? e}`); process.exitCode = 1; }
};

const msg = (seq, messageId, extra = {}) => ({ seq, messageId, sender: '群友', text: 'x', ...extra });

console.log('reply-target 单测：');

test('本轮快照里出现过的 id → 允许引用', () => {
  const seen = new Map();
  noteSeenRefs(seen, 'group:1', [msg(10, '-111'), msg(11, '222')]);
  assert.equal(looksUnseen(seen.get('group:1'), null, '-111'), false);
  assert.equal(looksUnseen(seen.get('group:1'), null, '222'), false);
});

test('seq 也可以作为引用目标', () => {
  const seen = new Map();
  noteSeenRefs(seen, 'group:1', [msg(10, '-111')]);
  assert.equal(looksUnseen(seen.get('group:1'), null, '10'), false);
});

test('上一轮见过、本轮快照没有的旧 id → 丢弃（核心回归）', () => {
  const seen = new Map();
  noteSeenRefs(seen, 'group:1', [msg(10, '-111')]);
  // 新一轮：同一个 key 重置后只看到 seq 20-22
  seen.delete('group:1');
  noteSeenRefs(seen, 'group:1', [msg(20, '333'), msg(21, '444'), msg(22, '555')]);
  assert.equal(looksUnseen(seen.get('group:1'), null, '-111'), true);
});

test('当前未读缓冲里的消息也算见过', () => {
  const st = { unread: [msg(30, '999')], recentMessages: [] };
  assert.equal(looksUnseen(new Map(), st, '999'), false);
  assert.equal(looksUnseen(new Map(), st, '30'), false);
});

test('最近 10 条历史消息（含自己刚发的）允许引用', () => {
  const recent = Array.from({ length: 12 }, (_, i) => msg(i + 1, `m${i + 1}`));
  const st = { unread: [], recentMessages: recent };
  assert.equal(looksUnseen(new Map(), st, 'm12'), false);       // 最后一条
  assert.equal(looksUnseen(new Map(), st, `m${12 - RECENT_TAIL + 2}`), false); // 尾部范围内
  assert.equal(looksUnseen(new Map(), st, 'm1'), true);         // 太旧
});

test('空引用不拦（交给原有校验处理）', () => {
  assert.equal(looksUnseen(new Map(), null, ''), false);
  assert.equal(looksUnseen(new Map(), null, undefined), false);
});

test('集合有上限，但最近写入的不会被挤掉', () => {
  const seen = new Map();
  const many = Array.from({ length: 300 }, (_, i) => msg(i + 1, `id${i + 1}`));
  noteSeenRefs(seen, 'group:1', many);
  const map = seen.get('group:1');
  assert.ok(map.size <= 200, `集合应被裁剪，实际 ${map.size}`);
  assert.ok(map.has('id300'), '最新写入的必须保留');
});

console.log(`\n通过 ${passed} 项。`);
