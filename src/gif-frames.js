// 动图（GIF）→ 九宫格静态图：让视觉模型"看到动画"而不是只看首帧。
//
// 为什么需要：DSH/模型链路会把动图归一化成静态首帧（实测 300x300 GIF 读回来是
// image/webp 300x300 单帧），所以"给模型一个 GIF"没有意义。桥接侧先把帧抽出来、
// 按时间顺序拼成一张网格 PNG，模型就能一次看到整段动作。
//
// 设计要点：
// - **帧数自适应**：表情包常见 2~8 帧，硬要 9 格会有大片空白。这里按实际帧数选布局
//   （2→1x2、3→1x3、4→2x2、5~6→2x3、7~9→3x3），超过 9 帧均匀采样到 9。
// - 单帧 GIF 不处理（返回 null，调用方原样透传），不浪费 token。
// - 自己做 GIF 合成：gifuct 只给每帧的矩形补丁（patch），必须按 disposal 规则
//   合成完整画面，否则子矩形优化的动图会缺块。
// - 缩放用区域平均（box filter），比最近邻干净；输出白底，避免透明被渲染成黑块。
// - 任何异常（畸形 GIF / 解帧失败）都返回 null，调用方回退首帧 —— 看图不能因此挂掉。
//
// 依赖：gifuct-js（MIT，纯 JS 解码）、pngjs（MIT，纯 JS 编码）。

import { parseGIF, decompressFrames } from 'gifuct-js';
import { PNG } from 'pngjs';

export const GIF_DEFAULTS = Object.freeze({
  enabled: true,
  frames: 9,        // 最多几格（1~9）
  cellPx: 224,      // 每格边长（输出上限见 MAX_OUTPUT_SIDE）
  onlyAnimated: true,
  background: '#ffffff'
});

const MAX_OUTPUT_SIDE = 1024;

export function normalizeGifConfig(raw) {
  const src = raw && typeof raw === 'object' && !Array.isArray(raw) ? raw : {};
  const clamp = (v, fallback, min, max) => {
    const n = Number(v);
    return Number.isFinite(n) ? Math.min(max, Math.max(min, Math.round(n))) : fallback;
  };
  return {
    ...GIF_DEFAULTS,
    ...src,
    enabled: src.enabled !== false,
    frames: clamp(src.frames, GIF_DEFAULTS.frames, 1, 9),
    cellPx: clamp(src.cellPx, GIF_DEFAULTS.cellPx, 64, 512),
    onlyAnimated: src.onlyAnimated !== false,
    background: /^#[0-9a-f]{6}$/i.test(String(src.background ?? '')) ? String(src.background) : GIF_DEFAULTS.background
  };
}

/** GIF 魔数判断（GIF87a / GIF89a）。 */
export function isGif(buf) {
  if (!buf || buf.length < 6) return false;
  const head = Buffer.isBuffer(buf) ? buf.subarray(0, 6).toString('latin1') : '';
  return head === 'GIF87a' || head === 'GIF89a';
}

function parseColor(hex) {
  const s = String(hex || '#ffffff').replace('#', '');
  return [parseInt(s.slice(0, 2), 16), parseInt(s.slice(2, 4), 16), parseInt(s.slice(4, 6), 16), 255];
}

function fillRect(canvas, w, h, rect, color) {
  const x0 = Math.max(0, rect.left | 0);
  const y0 = Math.max(0, rect.top | 0);
  const x1 = Math.min(w, x0 + (rect.width | 0));
  const y1 = Math.min(h, y0 + (rect.height | 0));
  for (let y = y0; y < y1; y++) {
    for (let x = x0; x < x1; x++) {
      const i = (y * w + x) * 4;
      canvas[i] = color[0]; canvas[i + 1] = color[1]; canvas[i + 2] = color[2]; canvas[i + 3] = 255;
    }
  }
}

/** 把一帧的 RGBA 补丁按 alpha 合成到画布上。 */
function blitPatch(canvas, w, h, frame) {
  const { left, top, width, height } = frame.dims;
  const patch = frame.patch;
  for (let y = 0; y < height; y++) {
    const cy = top + y;
    if (cy < 0 || cy >= h) continue;
    for (let x = 0; x < width; x++) {
      const cx = left + x;
      if (cx < 0 || cx >= w) continue;
      const si = (y * width + x) * 4;
      const a = patch[si + 3] / 255;
      if (a <= 0) continue;
      const di = (cy * w + cx) * 4;
      canvas[di] = Math.round(patch[si] * a + canvas[di] * (1 - a));
      canvas[di + 1] = Math.round(patch[si + 1] * a + canvas[di + 1] * (1 - a));
      canvas[di + 2] = Math.round(patch[si + 2] * a + canvas[di + 2] * (1 - a));
      canvas[di + 3] = 255;
    }
  }
}

/** 区域平均缩放（RGBA，跳过透明像素按前景权重平均）。 */
function scaleImage(src, sw, sh, dw, dh) {
  const out = new Uint8ClampedArray(dw * dh * 4);
  for (let y = 0; y < dh; y++) {
    const sy0 = Math.floor((y * sh) / dh);
    const sy1 = Math.max(sy0 + 1, Math.ceil(((y + 1) * sh) / dh));
    for (let x = 0; x < dw; x++) {
      const sx0 = Math.floor((x * sw) / dw);
      const sx1 = Math.max(sx0 + 1, Math.ceil(((x + 1) * sw) / dw));
      let r = 0; let g = 0; let b = 0; let a = 0; let n = 0;
      for (let sy = sy0; sy < Math.min(sy1, sh); sy++) {
        for (let sx = sx0; sx < Math.min(sx1, sw); sx++) {
          const i = (sy * sw + sx) * 4;
          const alpha = src[i + 3] / 255;
          r += src[i] * alpha; g += src[i + 1] * alpha; b += src[i + 2] * alpha; a += alpha; n++;
        }
      }
      const di = (y * dw + x) * 4;
      if (a > 0) {
        out[di] = Math.round(r / a); out[di + 1] = Math.round(g / a); out[di + 2] = Math.round(b / a);
      } else {
        out[di] = 255; out[di + 1] = 255; out[di + 2] = 255;
      }
      out[di + 3] = 255;
    }
  }
  return out;
}

/** 帧数 → 网格布局（列少行多更好看：2 帧横排、3 帧横排、4 帧田字）。 */
export function gridLayout(count, maxFrames = 9) {
  const n = Math.max(1, Math.min(maxFrames, Number(count) || 1));
  if (n === 1) return { cols: 1, rows: 1, capacity: 1 };
  if (n === 2) return { cols: 2, rows: 1, capacity: 2 };
  if (n === 3) return { cols: 3, rows: 1, capacity: 3 };
  if (n === 4) return { cols: 2, rows: 2, capacity: 4 };
  if (n <= 6) return { cols: 3, rows: 2, capacity: 6 };
  return { cols: 3, rows: 3, capacity: 9 };
}

/** 从 N 帧里均匀挑出最多 k 帧（含首尾）。 */
export function sampleIndices(total, k) {
  const n = Math.max(1, Math.min(total, k));
  if (total <= n) return Array.from({ length: total }, (_, i) => i);
  if (n === 1) return [0];
  const out = [];
  for (let i = 0; i < n; i++) out.push(Math.round((i * (total - 1)) / (n - 1)));
  return [...new Set(out)];
}

/**
 * 把 GIF 合成成网格 PNG。
 * @returns {{png: Buffer, width: number, height: number, frames: number, cells: number, totalFrames: number}|null}
 */
export function composeGifGrid(buf, rawOpts = {}) {
  const opts = normalizeGifConfig(rawOpts);
  if (!opts.enabled) return null;
  if (!isGif(buf)) return null;
  let gif;
  let frames;
  try {
    gif = parseGIF(buf);
    frames = decompressFrames(gif, true);
  } catch {
    return null;
  }
  if (!Array.isArray(frames) || frames.length === 0) return null;
  if (opts.onlyAnimated && frames.length <= 1) return null;

  const totalFrames = frames.length;
  // window: [startRatio, endRatio]，用于把长动画分段看（默认全段）。
  const win = Array.isArray(opts.window) && opts.window.length === 2 ? opts.window.map(Number) : [0, 1];
  const lo = Math.max(0, Math.min(totalFrames - 1, Math.floor(totalFrames * win[0])));
  const hi = Math.max(lo + 1, Math.min(totalFrames, Math.ceil(totalFrames * win[1])));
  const layout = gridLayout(Math.min(hi - lo, opts.frames), opts.frames);
  const picked = new Set(sampleIndices(hi - lo, layout.capacity).map((i) => i + lo));
  const W = Math.max(1, Number(gif.lsd?.width) || 0);
  const H = Math.max(1, Number(gif.lsd?.height) || 0);
  if (!W || !H) return null;

  const bg = parseColor(opts.background);
  const canvas = new Uint8ClampedArray(W * H * 4);
  for (let i = 0; i < canvas.length; i += 4) {
    canvas[i] = bg[0]; canvas[i + 1] = bg[1]; canvas[i + 2] = bg[2]; canvas[i + 3] = 255;
  }

  const cell = Math.max(32, Math.min(opts.cellPx, Math.floor(MAX_OUTPUT_SIDE / Math.max(layout.cols, layout.rows))));
  const outW = layout.cols * cell;
  const outH = layout.rows * cell;
  const out = new Uint8ClampedArray(outW * outH * 4);
  for (let i = 0; i < out.length; i += 4) {
    out[i] = bg[0]; out[i + 1] = bg[1]; out[i + 2] = bg[2]; out[i + 3] = 255;
  }

  let prevRect = null;
  let prevDisposal = 0;
  let backup = null;
  let cellIndex = 0;
  let captured = 0;

  for (let i = 0; i < frames.length; i++) {
    const frame = frames[i];
    if (!frame?.patch || !frame?.dims) continue;
    // 应用上一帧的 disposal
    if (prevDisposal === 2 && prevRect) fillRect(canvas, W, H, prevRect, bg);
    else if (prevDisposal === 3 && backup) canvas.set(backup);
    // disposal 3 需要"画这一帧之前"的快照
    if (frame.disposalType === 3) backup = canvas.slice();
    blitPatch(canvas, W, H, frame);
    prevRect = frame.dims;
    prevDisposal = Number(frame.disposalType) || 0;

    if (!picked.has(i)) continue;
    // 等比缩放到格子内（居中、白底）
    const scale = Math.min(cell / W, cell / H);
    const dw = Math.max(1, Math.round(W * scale));
    const dh = Math.max(1, Math.round(H * scale));
    const scaled = scaleImage(canvas, W, H, dw, dh);
    const ox = Math.round((cell * (cellIndex % layout.cols)) + (cell - dw) / 2);
    const oy = Math.round((cell * Math.floor(cellIndex / layout.cols)) + (cell - dh) / 2);
    for (let y = 0; y < dh; y++) {
      const ty = oy + y;
      if (ty < 0 || ty >= outH) continue;
      for (let x = 0; x < dw; x++) {
        const tx = ox + x;
        if (tx < 0 || tx >= outW) continue;
        const si = (y * dw + x) * 4;
        const di = (ty * outW + tx) * 4;
        out[di] = scaled[si]; out[di + 1] = scaled[si + 1]; out[di + 2] = scaled[si + 2]; out[di + 3] = 255;
      }
    }
    cellIndex++;
    captured++;
    if (cellIndex >= layout.capacity) break;
  }
  if (!captured) return null;

  const png = new PNG({ width: outW, height: outH });
  png.data = Buffer.from(out.buffer, out.byteOffset, out.length);
  return {
    png: PNG.sync.write(png),
    width: outW,
    height: outH,
    frames: totalFrames,
    cells: captured,
    totalFrames,
    cols: layout.cols,
    rows: layout.rows
  };
}
