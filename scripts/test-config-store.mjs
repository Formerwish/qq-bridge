// 配置存储（TOML 权威 / JSON 过渡镜像）单测。
//
// 覆盖：TOML 序列化往返、null 剔除（TOML 不支持 null）、TOML/JSON 双读、
// 写回 + 镜像同步、坏文件必须抛错而不是静默回空。

import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {
  toToml, loadConfigDocument, readConfigRaw, writeConfigDocument, syncConfigMirror,
  setConfigRoot, configPath, configTomlPath, configJsonPath
} from '../src/config-store.js';

let passed = 0;
function test(name, fn) {
  try { fn(); passed++; console.log(`  ✓ ${name}`); }
  catch (e) { console.error(`  ✗ ${name}\n    ${e?.message ?? e}`); process.exitCode = 1; }
}

const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'qq-config-store-'));
setConfigRoot(temp);

const sample = {
  ownerQQ: 123456,
  consoleToken: 'tok',
  dsh: { model: 'deepseek-flash', reasoningEffort: 'high', nested: { flag: true } },
  allow: { private: ['1', '2'], groups: [111, 222] },
  periods: [
    { name: 'peak', start: '08:30', end: '00:30', replyProbability: 0.6 },
    { name: 'off-peak', start: '00:30', end: '08:30', replyProbability: 0.9 }
  ],
  emptyList: [],
  nothing: null
};

console.log('config-store 单测：');

test('TOML 往返一致（数组表 / 嵌套表 / 数字 / 布尔）', () => {
  const back = loadConfigDocument(writeFixture(toToml(sample))).data;
  assert.equal(back.ownerQQ, 123456);
  assert.deepEqual(back.allow.private, ['1', '2']);
  assert.deepEqual(back.periods.map((p) => p.name), ['peak', 'off-peak']);
  assert.equal(back.dsh.nested.flag, true);
});

test('null 字段被剔除（TOML 无 null，直接写会抛）', () => {
  const text = toToml(sample);
  assert.ok(!text.includes('nothing'), 'null 字段不应出现在 TOML 里');
  const back = loadConfigDocument(writeFixture(text)).data;
  assert.equal('nothing' in back, false);
});

test('configPath 优先 TOML，再回退 JSON', () => {
  fs.rmSync(configTomlPath(), { force: true });
  fs.rmSync(configJsonPath(), { force: true });
  fs.writeFileSync(configJsonPath(), JSON.stringify({ ownerQQ: 7 }), 'utf8');
  assert.equal(configPath(), configJsonPath());
  assert.equal(loadConfigDocument().data.ownerQQ, 7);
  fs.writeFileSync(configTomlPath(), toToml({ ownerQQ: 9 }), 'utf8');
  assert.equal(configPath(), configTomlPath());
  assert.equal(loadConfigDocument().data.ownerQQ, 9);
});

test('写回同时更新 TOML 与 JSON 镜像', () => {
  writeConfigDocument({ ownerQQ: 42, consoleToken: 'x' });
  assert.match(fs.readFileSync(configTomlPath(), 'utf8'), /ownerQQ = 42/);
  assert.equal(JSON.parse(fs.readFileSync(configJsonPath(), 'utf8')).ownerQQ, 42);
});

test('syncConfigMirror 幂等且能修好过期镜像', () => {
  writeConfigDocument({ ownerQQ: 42 });
  fs.writeFileSync(configJsonPath(), JSON.stringify({ ownerQQ: 1 }), 'utf8');
  assert.equal(syncConfigMirror().updated, true);
  assert.equal(JSON.parse(fs.readFileSync(configJsonPath(), 'utf8')).ownerQQ, 42);
  assert.equal(syncConfigMirror().updated, false);
});

test('坏 TOML / 顶层不是表 → 抛错（readConfigRaw 回退）', () => {
  fs.writeFileSync(configTomlPath(), 'this is not toml = = =', 'utf8');
  assert.throws(() => loadConfigDocument());
  assert.deepEqual(readConfigRaw({ fallback: true }), { fallback: true });
});

function writeFixture(text) {
  fs.writeFileSync(configTomlPath(), text, 'utf8');
  return configTomlPath();
}

console.log(`\n通过 ${passed} 项。`);
