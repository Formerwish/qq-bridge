// 把历史上用过的表情一次性标记为“常用”（useCount > 0）。
// 用法：node scripts/seed-sticker-favorites.mjs [--min 1]
import fs from 'node:fs';
import path from 'node:path';

const ROOT = 'E:/qq-bridge';
const minArg = process.argv.indexOf('--min');
const min = minArg >= 0 ? Number(process.argv[minArg + 1]) : 1;

const cfg = fs.readFileSync(path.join(ROOT, 'config.toml'), 'utf8');
const token = (cfg.match(/^consoleToken\s*=\s*"([^"]+)"/m) || [])[1];
if (!token) throw new Error('config.toml 缺 consoleToken');

const stickers = JSON.parse(fs.readFileSync(path.join(ROOT, 'state/stickers.json'), 'utf8'));
const targets = stickers.filter((s) => Number(s.useCount || 0) >= min && s.favorite !== true);
console.log(`共 ${stickers.length} 个表情，useCount>=${min} 的 ${targets.length} 个将标记为常用`);

let ok = 0;
for (const s of targets) {
  const resp = await fetch('http://127.0.0.1:3100/internal/stickers/note', {
    method: 'POST',
    headers: { 'x-control-token': token, 'content-type': 'application/json' },
    body: JSON.stringify({ id: s.id, favorite: true })
  });
  if (resp.ok) ok++;
  await new Promise((r) => setTimeout(r, 30));
}
console.log(`完成：标记 ${ok} 个`);
