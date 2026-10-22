// 扫描全部收藏表情的运动幅度（横向/纵向重心移动），用于找出"描述没体现动作"的候选。
// 输出 state/sticker-motion.json + 控制台摘要。
import fs from 'node:fs';
import path from 'node:path';
import { parseGIF, decompressFrames } from 'gifuct-js';

const ROOT = 'E:/qq-bridge';
const cfg = fs.readFileSync(path.join(ROOT, 'config.toml'), 'utf8');
const token = (cfg.match(/^consoleToken\s*=\s*"([^"]+)"/m) || [])[1];
const stickers = JSON.parse(fs.readFileSync(path.join(ROOT, 'state/stickers.json'), 'utf8'));
const out = {};

function analyze(buf) {
  const gif = parseGIF(buf);
  const frames = decompressFrames(gif, true);
  const W = gif.lsd.width, H = gif.lsd.height;
  const canvas = new Uint8ClampedArray(W * H * 4);
  for (let i = 0; i < canvas.length; i += 4) { canvas[i] = canvas[i + 1] = canvas[i + 2] = 255; canvas[i + 3] = 255; }
  let prevRect = null, prevDisposal = 0, backup = null;
  const cx = [], cy = [];
  for (const frame of frames) {
    if (!frame?.patch) continue;
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
    let sx = 0, sy = 0, n = 0;
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
      const i = (y * W + x) * 4;
      if (canvas[i] + canvas[i + 1] + canvas[i + 2] < 300) { sx += x; sy += y; n++; }
    }
    if (n) { cx.push(sx / n); cy.push(sy / n); }
  }
  const amp = (arr) => (arr.length ? Math.max(...arr) - Math.min(...arr) : 0);
  return { frames: frames.length, ampX: +amp(cx).toFixed(1), ampY: +amp(cy).toFixed(1) };
}

let done = 0, failed = 0;
for (const sticker of stickers) {
  const id = String(sticker.id);
  try {
    const resp = await fetch(`http://127.0.0.1:3100/internal/stickers/image?id=${encodeURIComponent(id)}`, {
      headers: { 'x-control-token': token }
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const buf = Buffer.from(await resp.arrayBuffer());
    out[id] = analyze(buf);
    done++;
    if (done % 20 === 0) console.log(`  已分析 ${done}…`);
  } catch (error) {
    failed++;
    console.log(`  ✗ ${id.slice(-10)}: ${error.message}`);
  }
}
fs.writeFileSync(path.join(ROOT, 'state/sticker-motion.json'), JSON.stringify(out, null, 2));
const big = Object.entries(out).filter(([, v]) => v.ampX >= 8 || v.ampY >= 8);
const verbs = /摇|晃|摆|点|转|抖|跳|甩|翻|滚|走|跑|挥|捶|拍|推|拉|丢|撞|弹/;
const suspicious = big.filter(([id]) => {
  const s = stickers.find((x) => String(x.id) === id);
  return s && !verbs.test(s.localNote || '');
});
console.log(`完成：分析 ${done}，失败 ${failed}；幅度>=8px 的 ${big.length} 个；其中描述缺动作词的 ${suspicious.length} 个`);
fs.writeFileSync(path.join(ROOT, 'state/sticker-suspicious.json'), JSON.stringify(suspicious.map(([id, v]) => ({ id, ...v })), null, 2));
