// 针对单个表情做"分段密集采样"，用于核对动作（例如摇头/点头这种短周期动作）。
// 用法：node scripts/sticker-inspect.mjs <sticker-id>
import fs from 'node:fs';
import path from 'node:path';
import { composeGifGrid } from '../src/gif-frames.js';

const ROOT = 'E:/qq-bridge';
const id = process.argv[2];
if (!id) { console.error('用法: node scripts/sticker-inspect.mjs <id>'); process.exit(1); }

const cfg = fs.readFileSync(path.join(ROOT, 'config.toml'), 'utf8');
const token = (cfg.match(/^consoleToken\s*=\s*"([^"]+)"/m) || [])[1];
const resp = await fetch(`http://127.0.0.1:3100/internal/stickers/image?id=${encodeURIComponent(id)}`, {
  headers: { 'x-control-token': token }
});
if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
const buf = Buffer.from(await resp.arrayBuffer());

const outDir = path.join(ROOT, 'state/sticker-grids/inspect');
fs.mkdirSync(outDir, { recursive: true });
for (const [tag, win] of [['a', [0, 0.6]], ['b', [0.4, 1.0]]]) {
  const grid = composeGifGrid(buf, { frames: 9, cellPx: 224, window: win });
  if (!grid) throw new Error('不是动图/解码失败');
  const file = path.join(outDir, `${id}-${tag}.png`);
  fs.writeFileSync(file, grid.png);
  console.log(tag, win.join('-'), 'frames', grid.frames, '->', file);
}
