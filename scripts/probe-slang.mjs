// 黑话库真库探针：验证 kb_slang 的读、写（对账）、统计，不连接 QQ。
//
// 用途：桥接改成 DB 存储后，确认 SQL 与表结构真的对得上（`usage` 是 MySQL 保留字，
// 这类问题只有真库能暴露）。写入是**幂等对账**：把库里已有的条目原样同步一遍，
// 不会改内容、不会删数据；updated_ms 相同，GREATEST 保持原值。
//
// 运行：node scripts/probe-slang.mjs [--sync]

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createSlangDb } from '../src/slang-db.js';

const root = fileURLToPath(new URL('..', import.meta.url));
const args = process.argv.slice(2);
const doSync = args.includes('--sync');

let cfgFile;
try {
  cfgFile = JSON.parse(fs.readFileSync(path.join(root, 'config.json'), 'utf8'));
} catch (error) {
  console.error(`读不到 config.json：${error?.message ?? error}`);
  process.exit(1);
}
const mysql = cfgFile.kb?.mysql;
if (!mysql) {
  console.error('config.json 缺少 kb.mysql（黑话库复用它作为连接参数）');
  process.exit(1);
}

const db = createSlangDb(mysql, { rawSlangCfg: cfgFile.slang?.store, log: (m) => console.warn(m) });
console.log(`目标：${mysql.user}@${mysql.host}:${mysql.port}/${mysql.database}（enabled=${db.enabled}）`);

let failed = false;
const stats = await db.stats();
console.log('\n[统计]', JSON.stringify(stats, null, 2));
if (!stats.ok) failed = true;

const loaded = await db.loadAll();
if (!loaded.ok) {
  console.error('\n读库失败：检查 kb.mysql 与 kb_slang 表（先跑 E:\\qq-kb-admin\\migrate.py）。');
  process.exit(1);
}
console.log(`\n[读库] ${loaded.entries.length} 条；最近 5 条：`);
for (const e of loaded.entries.slice(0, 5)) {
  console.log(`  ${e.status.padEnd(9)} ${e.content}  → ${e.meaning || '（无含义）'}  (count=${e.count})`);
}

if (doSync) {
  const res = await db.sync(loaded.entries);
  console.log('\n[对账]', JSON.stringify(res));
  if (!res.ok) failed = true;
} else {
  console.log('\n[对账] 已跳过（加 --sync 执行一次幂等对账，验证 INSERT/UPDATE 语句）');
}

db.close();
console.log(failed ? '\n探针失败。' : '\n探针通过。');
process.exit(failed ? 1 : 0);
