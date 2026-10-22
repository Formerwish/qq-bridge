// 一次性迁移：config.json → config.toml（TOML 为唯一权威文件）。
//
// 用法：
//   node scripts/migrate-config.mjs            # 迁移（已存在 config.toml 时只校验）
//   node scripts/migrate-config.mjs --dry-run  # 只打印将要写入的 TOML 与差异统计
//   node scripts/migrate-config.mjs --force    # 覆盖已存在的 config.toml（先备份）
//
// 行为：
//   1) 读 config.json；顶层不是对象则拒绝（绝不写坏配置）。
//   2) 备份 config.json → state/config.json.bak-<时间戳>（state 已在 .gitignore）。
//   3) 写 config.toml（带头部注释），并生成同值 JSON 镜像（过渡期供未迁移脚本读取）。
//   4) 校验：读回 config.toml，深比较与源对象一致（忽略 null 剔除），不一致则退出码 1。
//   5) 最后把原 config.json 改名为 config.json.migrated（保留可回滚，不参与运行）。

import fs from 'node:fs';
import path from 'node:path';
import { loadConfigDocument, writeConfigDocument, toToml, CONFIG_TOML, CONFIG_JSON, ROOT } from '../src/config-store.js';

const args = new Set(process.argv.slice(2));
const dryRun = args.has('--dry-run');
const force = args.has('--force');

function stamp() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
}

function deepEqual(a, b) {
  if (a === b) return true;
  if (typeof a !== typeof b) return false;
  if (a === null || b === null) return false;
  if (Array.isArray(a) !== Array.isArray(b)) return false;
  if (typeof a !== 'object') return false;
  const ak = Object.keys(a);
  const bk = Object.keys(b);
  if (ak.length !== bk.length) return false;
  return ak.every((key) => deepEqual(a[key], b[key]));
}

const stateDir = path.join(ROOT, 'state');

if (!fs.existsSync(CONFIG_JSON)) {
  if (fs.existsSync(CONFIG_TOML)) {
    console.log(`[migrate-config] 已存在 config.toml，且没有 config.json，无需迁移：${CONFIG_TOML}`);
    process.exit(0);
  }
  console.error('[migrate-config] 找不到 config.json，也没有 config.toml；请从 config.example.toml 复制后手工填写。');
  process.exit(1);
}

let source;
try {
  source = loadConfigDocument(CONFIG_JSON).data;
} catch (error) {
  console.error(`[migrate-config] 读取 config.json 失败：${error?.message ?? error}`);
  process.exit(1);
}

const tomlText = toToml(source);
if (dryRun) {
  console.log(tomlText);
  console.log(`[migrate-config] dry-run：将写入 ${CONFIG_TOML}（${tomlText.length} 字符）`);
  process.exit(0);
}

if (fs.existsSync(CONFIG_TOML) && !force) {
  console.error(`[migrate-config] config.toml 已存在。确认要用 config.json 覆盖请加 --force（会先备份）。`);
  process.exit(1);
}

fs.mkdirSync(stateDir, { recursive: true });
const backup = path.join(stateDir, `config.json.bak-${stamp()}`);
fs.copyFileSync(CONFIG_JSON, backup);
console.log(`[migrate-config] 已备份 config.json → ${path.relative(ROOT, backup)}`);

const written = writeConfigDocument(source, { mirrorJson: true });
console.log(`[migrate-config] 已写入 ${path.relative(ROOT, written.toml)}`);
console.log(`[migrate-config] 已生成 JSON 镜像 ${path.relative(ROOT, written.json)}（过渡期用，P6 删除）`);

const roundTrip = loadConfigDocument(CONFIG_TOML).data;
if (!deepEqual(source, roundTrip)) {
  console.error('[migrate-config] 校验失败：config.toml 读回与源配置不一致（可能有 null/日期等 TOML 不支持的值）。');
  console.error('  原文件安全，未删除；请检查上面报错字段。');
  process.exit(1);
}

const migrated = `${CONFIG_JSON}.migrated`;
fs.rmSync(migrated, { force: true });
fs.renameSync(CONFIG_JSON, migrated);
console.log(`[migrate-config] 原 config.json 已改名 → ${path.basename(migrated)}（可回滚，不参与运行）`);
console.log('[migrate-config] 完成。之后请只编辑 config.toml。');
