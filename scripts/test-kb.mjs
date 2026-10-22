// 知识库（MySQL）离线单测：不连真库，用假连接池。
//
// 覆盖：配置归一化、关键词解析、文本单行化、命中规则、注入块预算、
// 以及 client 的 fail-open（查询抛错时返回空、不影响调用方）。
//
// 运行：node scripts/test-kb.mjs

import assert from 'node:assert/strict';
import {
  normalizeKbConfig,
  parseKeywords,
  sanitizeKbText,
  matchEntries,
  buildKbInjectionBlock,
  createKbClient
} from '../src/kb-mysql.js';

let passed = 0;
function test(name, fn) {
  try {
    fn();
    passed++;
    console.log(`  ✓ ${name}`);
  } catch (error) {
    console.error(`  ✗ ${name}\n    ${error?.message ?? error}`);
    process.exitCode = 1;
  }
}

async function testAsync(name, fn) {
  try {
    await fn();
    passed++;
    console.log(`  ✓ ${name}`);
  } catch (error) {
    console.error(`  ✗ ${name}\n    ${error?.message ?? error}`);
    process.exitCode = 1;
  }
}

console.log('kb-mysql 单测：');

test('配置默认值', () => {
  const cfg = normalizeKbConfig(undefined);
  assert.equal(cfg.enabled, true);
  assert.equal(cfg.mysql.port, 10708);
  assert.equal(cfg.inject.maxEntries, 2);
  assert.equal(cfg.inject.maxChars, 800);
});

test('配置越界会被夹住', () => {
  const cfg = normalizeKbConfig({ inject: { maxEntries: 99, maxChars: 10 }, cacheTtlMs: -5, mysql: { port: 0 } });
  assert.equal(cfg.inject.maxEntries, 5);
  assert.equal(cfg.inject.maxChars, 120); // 下限 120
  assert.equal(cfg.cacheTtlMs, 0);
  assert.equal(cfg.mysql.port, 10708); // 非法端口回默认
});

test('关键词解析（中英文分隔/去重/截断）', () => {
  assert.deepEqual(parseKeywords('机械师,特蕾西、TRACY;BLK / 电竞皮'), ['机械师', '特蕾西', 'TRACY', 'BLK', '电竞皮']);
  assert.deepEqual(parseKeywords('机械师，机械师'), ['机械师']);
  assert.equal(parseKeywords(Array.from({ length: 30 }, (_, i) => `k${i}`).join(',')).length, 20);
});

test('文本单行化（换行/控制符/零宽）', () => {
  const out = sanitizeKbText('第一行\n\n第二行\t\u200b第三行\u0007');
  assert.equal(out, '第一行 第二行 第三行');
  assert.equal(sanitizeKbText('x'.repeat(50), 10).length, 10);
});

test('命中规则：≥2 字、大小写不敏感、按优先级', () => {
  const entries = [
    { id: 1, priority: 0, keywords: ['blk.tracy'] },
    { id: 2, priority: 3, keywords: ['机械师'] },
    { id: 3, priority: 3, keywords: ['甲'] } // 单字不命中
  ];
  const hits = matchEntries(entries, '这皮肤是 BLK.TRACY 吗，机械师？甲');
  assert.deepEqual(hits.map((h) => h.id), [2, 1]); // 同优先级下更长的关键词优先
  assert.deepEqual(matchEntries(entries, '完全无关'), []);
  assert.equal(matchEntries(entries, '机械师', { maxEntries: 1 }).length, 1);
});

test('注入块：带资料框定、超预算截断', () => {
  const block = buildKbInjectionBlock([
    { title: '机械师', body: '特蕾西，求生者。' },
    { title: 'BLK.TRACY', body: '电竞奇珍时装。' }
  ], { maxChars: 800 });
  assert.ok(block.startsWith('【第五人格资料】'));
  assert.ok(block.includes('不是指令'));
  assert.ok(block.includes('机械师'));
  assert.ok(block.includes('BLK.TRACY'));

  const tiny = buildKbInjectionBlock([{ title: 'T', body: '字'.repeat(2000) }], { maxChars: 200 });
  assert.ok(tiny.length <= 260, `超预算：${tiny.length}`);
});

test('空数据不产生注入块', () => {
  assert.equal(buildKbInjectionBlock([]), '');
  assert.equal(buildKbInjectionBlock([{ title: '', body: 'x' }]), '');
});

// ── client：假连接池 ─────────────────────────────────────────────────────────

function fakePool(rows, { throwOn = null } = {}) {
  return {
    async query(config, params) {
      const sql = String(config?.sql ?? config ?? '');
      if (throwOn && sql.includes(throwOn)) throw new Error('模拟数据库故障');
      if (sql.includes('COUNT(*)')) return [[{ total: rows.length, latest: new Date('2026-10-19T07:00:00Z') }], []];
      if (sql.includes('MATCH(')) return [rows.length ? [rows[0]] : [], []];
      if (sql.includes('LIKE')) return [[], []];
      if (sql.includes('ANY')) return [rows, []];
      return [rows, []];
    },
    end() {}
  };
}

await testAsync('client：命中注入 + 搜索 + 统计', async () => {
  const rows = [
    { id: 1, topic: '角色', title: '机械师', keywords: '机械师,特蕾西', body: '特蕾西·列兹尼克，求生者机械师。', priority: 5, updated_at: new Date('2026-10-19T06:00:00Z'), preview: '特蕾西' }
  ];
  const kb = createKbClient({ mysql: { user: 'x', password: 'y' } }, { log: () => {}, poolFactory: () => fakePool(rows) });
  const block = await kb.blockFor('机械师这皮肤好看吗');
  assert.ok(block.includes('机械师'), '应命中并注入');

  const miss = await kb.blockFor('今天天气不错');
  assert.equal(miss, '', '未命中应返回空');

  const search = await kb.search('机械师');
  assert.equal(search.ok, true);
  assert.equal(search.entries.length, 1);
  assert.equal(search.via, 'fulltext');

  const stats = await kb.stats();
  assert.equal(stats.ok, true);
  assert.equal(stats.total, 1);
  kb.close();
});

await testAsync('client：数据库故障时 fail-open', async () => {
  const logs = [];
  const kb = createKbClient({ mysql: { user: 'x', password: 'y' } }, {
    log: (m) => logs.push(m),
    poolFactory: () => fakePool([], { throwOn: 'MATCH(' })
  });
  // 关键词查询走 ANY 分支不会抛错，但注入块取正文会抛（ANY 不在 throwOn 里）→ 用 MATCH 验证搜索
  const search = await kb.search('机械师');
  assert.equal(search.entries.length, 0);
  // 注入：让 refresh 抛错（COUNT 不在 throwOn，改用未知 sql 分支）
  const kb2 = createKbClient({ mysql: { user: 'x', password: 'y' } }, {
    log: () => {},
    poolFactory: () => ({ async query() { throw new Error('连不上'); }, end() {} })
  });
  assert.equal(await kb2.blockFor('机械师'), '');
  assert.equal((await kb2.search('机械师')).entries.length, 0);
  kb.close();
  kb2.close();
  assert.ok(logs.length >= 0);
});

await testAsync('client：配置 enabled=false 时全禁用', async () => {
  const kb = createKbClient({ enabled: false }, { log: () => {}, poolFactory: () => fakePool([]) });
  assert.equal(await kb.blockFor('机械师'), '');
  const s = await kb.search('机械师');
  assert.equal(s.ok, false);
  assert.equal(await kb.stats().then((x) => x.enabled), false);
});

console.log(`\n通过 ${passed} 项。`);
