// 黑话库（MySQL）离线单测：不连真库，用有状态假连接池。
//
// 覆盖：行↔条目映射、参数顺序、sync 的新增/更新/删除/「库里更新更晚就跳过」、
// protectIds 保护、replaceAll 导入。
//
// 运行：node scripts/test-slang-db.mjs

import assert from 'node:assert/strict';
import {
  slangRowToEntry,
  slangEntryToParams,
  createSlangDb,
  isSlangStoreEnabled
} from '../src/slang-db.js';

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

/** 假数据库：用 id 为键的内存表，按 SQL 关键字分派。 */
function fakeDb(initial = []) {
  const rows = new Map(initial.map((r) => [r.id, { ...r }]));
  return {
    rows,
    async query(config, params) {
      const sql = String(config?.sql ?? config ?? '');
      if (sql.startsWith('SELECT id, content, updated_ms FROM kb_slang')) {
        return [[...rows.values()].map((r) => ({ id: r.id, content: r.content, updated_ms: r.updated_ms })), []];
      }
      if (sql.includes('SELECT id, content, meaning')) {
        return [[...rows.values()].sort((a, b) => b.updated_ms - a.updated_ms), []];
      }
      if (sql.startsWith('SELECT COUNT(*)')) {
        const list = [...rows.values()];
        return [[{
          total: list.length,
          confirmed: list.filter((r) => r.status === 'confirmed').length,
          candidates: list.filter((r) => r.status === 'candidate').length,
          rejected: list.filter((r) => r.status === 'rejected').length,
          latest: new Date()
        }], []];
      }
      if (sql.startsWith('INSERT INTO kb_slang')) {
        const [id, content, meaning, usage, example, risk, status, source, count, sourcesJson, evidenceJson, lastInference, createdMs, updatedMs] = params;
        const old = rows.get(id);
        rows.set(id, {
          id, content, meaning, usage, example, risk, status, source, count,
          sources_json: sourcesJson, evidence_json: evidenceJson,
          last_inference_count: lastInference, created_ms: createdMs,
          updated_ms: old ? Math.max(old.updated_ms, updatedMs) : updatedMs
        });
        return [{ affectedRows: 1 }, []];
      }
      if (sql.startsWith('DELETE FROM kb_slang')) {
        rows.delete(params[0]);
        return [{ affectedRows: 1 }, []];
      }
      throw new Error(`假数据库不认识的 SQL: ${sql.slice(0, 40)}`);
    },
    end() {}
  };
}

const entry = (id, content, updatedMs, extra = {}) => ({
  id,
  content,
  meaning: `含义-${content}`,
  usage: '',
  example: '',
  risk: '',
  status: 'confirmed',
  source: 'ai',
  count: 1,
  sources: [],
  evidence: [],
  lastInferenceCount: 0,
  createdAt: new Date(updatedMs).toISOString(),
  updatedAt: new Date(updatedMs).toISOString(),
  ...extra
});

console.log('slang-db 单测：');

test('开关：false / {enabled:false} 都算关闭', () => {
  assert.equal(isSlangStoreEnabled(undefined), true);
  assert.equal(isSlangStoreEnabled(false), false);
  assert.equal(isSlangStoreEnabled({ enabled: false }), false);
});

test('数据库行 → 条目（JSON 还原 + 毫秒转 ISO）', () => {
  const row = {
    id: 'abc', content: '你沙溢丝', meaning: '你什么意思', usage: '吐槽', example: '', risk: '',
    status: 'confirmed', source: 'ai', count: 3,
    sources_json: '["群123456789"]', evidence_json: '[{"sender":"甲","text":"你沙溢丝"}]',
    last_inference_count: 1, created_ms: 1700000000000, updated_ms: 1700000005000
  };
  const e = slangRowToEntry(row);
  assert.equal(e.id, 'abc');
  assert.equal(e.usage, '吐槽');
  assert.deepEqual(e.sources, ['群123456789']);
  assert.equal(e.evidence[0].sender, '甲');
  assert.equal(e.createdAt, new Date(1700000000000).toISOString());
  assert.equal(e.updatedAt, new Date(1700000005000).toISOString());
});

test('条目 → SQL 参数（顺序与列一致，updated_ms 不小于 created_ms）', () => {
  const params = slangEntryToParams(entry('x', 'xswl', 1700000002000));
  assert.equal(params.length, 14);
  assert.equal(params[0], 'x');
  assert.equal(params[1], 'xswl');
  assert.equal(params[12], 1700000002000);
  assert.ok(params[13] >= params[12], 'updated_ms 必须 >= created_ms');

  // updatedAt 比 createdAt 还早（时钟回拨/旧数据）时，updated_ms 抬到 created_ms，避免被当成「很旧」。
  const weird = slangEntryToParams(entry('y', 'y', 1700000009000, { updatedAt: '2000-01-01T00:00:00.000Z' }));
  assert.equal(weird[13], weird[12]);
});

await testAsync('sync：空库全插入', async () => {
  const db = fakeDb();
  const client = createSlangDb({}, { poolFactory: () => db });
  const res = await client.sync([entry('a', 'xswl', 1000), entry('b', '秒选', 2000)]);
  assert.equal(res.inserted, 2);
  assert.equal(db.rows.size, 2);
});

await testAsync('sync：本地更新更晚 → 覆盖；库里更新更晚 → 跳过', async () => {
  const db = fakeDb([
    { id: 'a', content: 'xswl', updated_ms: 1000, status: 'candidate', meaning: '' },
    { id: 'b', content: '秒选', updated_ms: 9000, status: 'confirmed', meaning: '库里改过' }
  ]);
  const client = createSlangDb({}, { poolFactory: () => db });
  const res = await client.sync([entry('a', 'xswl', 5000), entry('b', '秒选', 3000)]);
  assert.equal(res.updated, 1, 'a 应该被更新');
  assert.equal(res.skippedNewer, 1, 'b 应该被跳过');
  assert.equal(db.rows.get('a').status, 'confirmed');
  assert.equal(db.rows.get('b').updated_ms, 9000, 'b 不能被旧数据覆盖');
});

await testAsync('sync：内存里没有的会被删，protectIds 里的不删', async () => {
  const db = fakeDb([
    { id: 'gone', content: '旧词', updated_ms: 1000 },
    { id: 'keep', content: '新词', updated_ms: 1000 }
  ]);
  const client = createSlangDb({}, { poolFactory: () => db });
  const res = await client.sync([], { protectIds: new Set(['keep']) });
  assert.equal(res.deleted, 0 === 0 ? 1 : 0);
  assert.ok(db.rows.has('keep'), '被保护的条目不能删');
  assert.ok(!db.rows.has('gone'), '未保护的应删除');
});

await testAsync('replaceAll：导入不覆盖更新更晚的行', async () => {
  const db = fakeDb([{ id: 'a', content: 'xswl', updated_ms: 9999, status: 'confirmed' }]);
  const client = createSlangDb({}, { poolFactory: () => db });
  const res = await client.replaceAll([entry('a', 'xswl', 1000)]);
  assert.equal(res.count, 1);
  assert.equal(db.rows.get('a').updated_ms, 9999, '数据库里的新版本不能被旧导入覆盖');
});

await testAsync('stats：状态计数', async () => {
  const db = fakeDb([
    { id: 'a', content: 'a', status: 'confirmed', updated_ms: 1 },
    { id: 'b', content: 'b', status: 'candidate', updated_ms: 1 }
  ]);
  const client = createSlangDb({}, { poolFactory: () => db });
  const s = await client.stats();
  assert.equal(s.ok, true);
  assert.equal(s.total, 2);
  assert.equal(s.confirmed, 1);
  assert.equal(s.candidates, 1);
});

await testAsync('数据库故障：sync 返回 skipped 而不抛错', async () => {
  const client = createSlangDb({}, {
    poolFactory: () => ({ async query() { throw new Error('连不上'); }, end() {} })
  });
  const res = await client.sync([entry('a', 'xswl', 1000)]);
  assert.equal(res.ok, false);
  assert.equal(res.skipped, true);
});

console.log(`\n通过 ${passed} 项。`);
