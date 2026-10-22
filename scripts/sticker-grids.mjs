// 批量把收藏表情转成九宫格 PNG（每格一路动画帧），供视觉模型重写描述。
// 用法：node scripts/sticker-grids.mjs [--limit N] [--force]
import fs from 'node:fs';
import path from 'node:path';
import { composeGifGrid } from '../src/gif-frames.js';

const ROOT = 'E:/qq-bridge';
const OUT = path.join(ROOT, 'state/sticker-grids');
const MANIFEST = path.join(OUT, 'manifest.json');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const args = process.argv.slice(2);
const limitArg = args.indexOf('--limit');
const limit = limitArg >= 0 ? Number(args[limitArg + 1]) : Infinity;
const force = args.includes('--force');

const cfgText = fs.readFileSync(path.join(ROOT, 'config.toml'), 'utf8');
const token = (cfgText.match(/^consoleToken\s*=\s*"([^"]+)"/m) || [])[1];
if (!token) throw new Error('config.toml 缺 consoleToken');

const stickers = JSON.parse(fs.readFileSync(path.join(ROOT, 'state/stickers.json'), 'utf8'));
fs.mkdirSync(OUT, { recursive: true });

const manifest = fs.existsSync(MANIFEST) ? JSON.parse(fs.readFileSync(MANIFEST, 'utf8')) : {};
let done = 0, skipped = 0, failed = 0;

for (const sticker of stickers.slice(0, limit)) {
  const id = String(sticker.id);
  const png = path.join(OUT, `${id}.png`);
  if (!force && fs.existsSync(png) && manifest[id]) { skipped++; continue; }
  try {
    const url = `http://127.0.0.1:3100/internal/stickers/image?id=${encodeURIComponent(id)}`;
    const resp = await fetch(url, { headers: { 'x-control-token': token } });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const buf = Buffer.from(await resp.arrayBuffer());
    const grid = composeGifGrid(buf, { frames: 9, cellPx: 224 });
    if (!grid) throw new Error('不是动图或解码失败');
    fs.writeFileSync(png, grid.png);
    manifest[id] = { frames: grid.frames, cells: grid.cells, cols: grid.cols, rows: grid.rows, note: sticker.localNote || '' };
    done++;
    if (done % 10 === 0) console.log(`  已生成 ${done} 个…`);
  } catch (error) {
    failed++;
    console.log(`  ✗ ${id.slice(-12)}: ${error.message}`);
  }
  await sleep(60);
}

fs.writeFileSync(MANIFEST, JSON.stringify(manifest, null, 2));
console.log(`完成：生成 ${done}，跳过 ${skipped}，失败 ${failed}，总计 ${Object.keys(manifest).length}`);
