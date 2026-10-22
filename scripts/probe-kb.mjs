// 知识库真库探针（只读）：检查连接、条目数、检索与注入效果。
//
// 用途：桥接/管理端改完后跑一遍，确认「库通了、关键词能命中、注入块长度正常」。
// 运行：node scripts/probe-kb.mjs [--query 机械师] [--text "这皮肤是机械师吗"]
// 需要 config.json 里有 kb 段（含 mysql 连接）；不会写库。

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createKbClient, normalizeKbConfig } from '../src/kb-mysql.js';

const root = fileURLToPath(new URL('..', import.meta.url));
const args = process.argv.slice(2);
const argOf = (name, fallback) => {
  const i = args.indexOf(name);
  return i >= 0 && args[i + 1] ? args[i + 1] : fallback;
};
const query = argOf('--query', '机械师');
const text = argOf('--text', '这皮肤是机械师吗？BLK.TRACY 跟初音谁像');

let cfgFile;
try {
  cfgFile = JSON.parse(fs.readFileSync(path.join(root, 'config.json'), 'utf8'));
} catch (error) {
  console.error(`读不到 config.json：${error?.message ?? error}`);
  process.exit(1);
}
const cfg = normalizeKbConfig(cfgFile.kb);
console.log(`目标：${cfg.mysql.user}@${cfg.mysql.host}:${cfg.mysql.port}/${cfg.mysql.database}（enabled=${cfg.enabled}）`);
if (!cfg.mysql.password) {
  console.log('提示：config.json 的 kb.mysql.password 为空，连不上多半是这里没填。');
}

const kb = createKbClient(cfgFile.kb, { log: (m) => console.warn(m) });
let failed = false;

const stats = await kb.stats();
console.log('\n[统计]', JSON.stringify(stats, null, 2));
if (!stats.ok) failed = true;

const search = await kb.search(query, { limit: 3 });
console.log(`\n[检索] q="${query}" ok=${search.ok} via=${search.via} total=${search.total}`);
for (const e of search.entries ?? []) {
  console.log(`  #${e.id} [${e.topic}] ${e.title}（priority ${e.priority}）\n    ${e.preview}`);
}
if (!search.ok) failed = true;

const block = await kb.blockFor(text);
console.log(`\n[注入] text="${text}"`);
if (!block) {
  console.log('  未命中任何关键词（桥接在这种情况下不会注入任何资料）。');
} else {
  console.log(`  命中 ${block.split('\n').length - 1} 条，共 ${block.length} 字：`);
  console.log(block);
  if (block.length > cfg.inject.maxChars + 40) {
    console.error(`  ✗ 注入块超出预算（${cfg.inject.maxChars}）：${block.length}`);
    failed = true;
  }
}

kb.close();
console.log(failed ? '\n探针失败：请检查 config.json 的 kb 段与 MySQL 状态。' : '\n探针通过。');
process.exit(failed ? 1 : 0);
