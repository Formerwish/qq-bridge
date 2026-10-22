// 动图 → 九宫格 单测（离线，用仓库里的 3 帧 GIF 夹具）。
//
// 覆盖：GIF 魔数、配置收敛、布局自适应（不足 9 帧不硬凑）、采样、PNG 输出、
//       关闭开关/非 GIF/损坏字节 必须返回 null（调用方回退首帧，不能抛错）。
//
// 运行：node scripts/test-gif-frames.mjs

import assert from 'node:assert/strict';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import {
  isGif, normalizeGifConfig, gridLayout, sampleIndices, composeGifGrid, GIF_DEFAULTS
} from '../src/gif-frames.js';

const fixture = fs.readFileSync(fileURLToPath(new URL('./fixtures/sticker-3frames.gif', import.meta.url)));

let passed = 0;
function test(name, fn) {
  try { fn(); passed++; console.log(`  ✓ ${name}`); }
  catch (e) { console.error(`  ✗ ${name}\n    ${e?.message ?? e}`); process.exitCode = 1; }
}

console.log('gif-frames 单测：');

test('GIF 魔数识别', () => {
  assert.equal(isGif(fixture), true);
  assert.equal(isGif(Buffer.from([0x89, 0x50, 0x4e, 0x47])), false);
  assert.equal(isGif(Buffer.alloc(0)), false);
});

test('配置收敛（帧数 1~9、格子 64~512）', () => {
  const cfg = normalizeGifConfig({ frames: 99, cellPx: 8, enabled: false });
  assert.equal(cfg.frames, 9);
  assert.equal(cfg.cellPx, 64);
  assert.equal(cfg.enabled, false);
  assert.equal(normalizeGifConfig(undefined).cellPx, GIF_DEFAULTS.cellPx);
});

test('布局自适应：不足 9 帧不硬凑格子', () => {
  assert.deepEqual([gridLayout(2).cols, gridLayout(2).rows], [2, 1]);
  assert.deepEqual([gridLayout(3).cols, gridLayout(3).rows], [3, 1]);
  assert.deepEqual([gridLayout(4).cols, gridLayout(4).rows], [2, 2]);
  assert.deepEqual([gridLayout(5).cols, gridLayout(5).rows], [3, 2]);
  assert.deepEqual([gridLayout(6).cols, gridLayout(6).rows], [3, 2]);
  assert.deepEqual([gridLayout(7).cols, gridLayout(7).rows], [3, 3]);
  assert.deepEqual([gridLayout(9).cols, gridLayout(9).rows], [3, 3]);
});

test('采样：含首尾、均匀、去重', () => {
  assert.deepEqual(sampleIndices(3, 9), [0, 1, 2]);       // 帧数不够就全要
  assert.deepEqual(sampleIndices(10, 9), [0, 1, 2, 3, 5, 6, 7, 8, 9]);
  const s = sampleIndices(39, 9);
  assert.equal(s[0], 0);
  assert.equal(s.at(-1), 38);
  assert.equal(new Set(s).size, s.length);
});

test('3 帧 GIF → 3x1 网格 PNG', () => {
  const res = composeGifGrid(fixture, { cellPx: 224 });
  assert.ok(res, '应生成网格');
  assert.equal(res.frames, 3);
  assert.equal(res.cells, 3);
  assert.equal(res.width, 224 * 3);
  assert.equal(res.height, 224 * 1);
  assert.equal(res.png.subarray(1, 4).toString('latin1'), 'PNG');
});

test('单帧/关闭/非 GIF/损坏 → null（回退首帧，不抛错）', () => {
  assert.equal(composeGifGrid(fixture, { enabled: false }), null);
  assert.equal(composeGifGrid(Buffer.from('not a gif at all'), {}), null);
  const broken = Buffer.from(fixture);
  broken[10] = 0; broken[11] = 0; // 破坏逻辑屏幕尺寸
  assert.doesNotThrow(() => composeGifGrid(broken, {}));
});

test('输出边长不超过 1024（3x3 时每格自动收窄）', () => {
  const res = composeGifGrid(fixture, { cellPx: 512, frames: 9 });
  assert.ok(res);
  assert.ok(res.width <= 1024 && res.height <= 1024, `${res.width}x${res.height}`);
});

console.log(`\n通过 ${passed} 项。`);
