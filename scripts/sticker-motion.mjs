// 分析单个表情每帧的水平重心，用来判断是否存在"左右摇头"这类短周期动作。
import fs from 'node:fs';
import path from 'node:path';
import { parseGIF, decompressFrames } from 'gifuct-js';

const ROOT = 'E:/qq-bridge';
const id = process.argv[2];
const cfg = fs.readFileSync(path.join(ROOT, 'config.toml'), 'utf8');
const token = (cfg.match(/^consoleToken\s*=\s*"([^"]+)"/m) || [])[1];
const resp = await fetch(`http://127.0.0.1:3100/internal/stickers/image?id=${encodeURIComponent(id)}`, {
  headers: { 'x-control-token': token }
});
const buf = Buffer.from(await resp.arrayBuffer());
const gif = parseGIF(buf);
const frames = decompressFrames(gif, true);
const W = gif.lsd.width, H = gif.lsd.height;
const canvas = new Uint8ClampedArray(W * H * 4);
let prevRect = null, prevDisposal = 0, backup = null;
const xs = [];
frames.forEach((frame) => {
  if (!frame?.patch) return;
  if (prevDisposal === 2 && prevRect) {
    for (let y = prevRect.top; y < prevRect.top + prevRect.height; y++)
      for (let x = prevRect.left; x < prevRect.left + prevRect.width; x++) {
        const i = (y * W + x) * 4; canvas[i] = canvas[i + 1] = canvas[i + 2] = 255; canvas[i + 3] = 255;
      }
  } else if (prevDisposal === 3 && backup) canvas.set(backup);
  if (frame.disposalType === 3) backup = canvas.slice();
  const { left, top, width, height } = frame.dims;
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
    const si = (y * width + x) * 4, a = frame.patch[si + 3] / 255;
    if (a <= 0) continue;
    const di = ((top + y) * W + (left + x)) * 4;
    canvas[di] = frame.patch[si]; canvas[di + 1] = frame.patch[si + 1]; canvas[di + 2] = frame.patch[si + 2]; canvas[di + 3] = 255;
  }
  prevRect = frame.dims; prevDisposal = Number(frame.disposalType) || 0;
  // 深色（帽子/头发）像素重心：只看上半部分，避免身体干扰
  let sum = 0, n = 0;
  for (let y = 0; y < Math.floor(H * 0.55); y++) {
    for (let x = 0; x < W; x++) {
      const i = (y * W + x) * 4;
      const r = canvas[i], g = canvas[i + 1], b = canvas[i + 2];
      if (r + g + b < 300) { sum += x; n++; }
    }
  }
  xs.push(n ? sum / n : NaN);
});
const valid = xs.filter((v) => Number.isFinite(v));
const mean = valid.reduce((a, b) => a + b, 0) / valid.length;
const min = Math.min(...valid), max = Math.max(...valid);
console.log('帧数:', frames.length, '重心x: mean', mean.toFixed(1), 'range', min.toFixed(1), '-', max.toFixed(1), '振幅', (max - min).toFixed(1));
console.log('序列:', xs.map((v) => v.toFixed(1)).join(' '));
