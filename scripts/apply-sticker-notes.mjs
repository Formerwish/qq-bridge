// 把新的 localNote 写回桥接表情库（保留 tags/useCount）。
// 用法：node scripts/apply-sticker-notes.mjs <notes.json>
//   notes.json 形如 {"notes":{"<id>":"描述"}} 或 {"<id>":"描述"}
import fs from 'node:fs';
import path from 'node:path';

const ROOT = 'E:/qq-bridge';
const file = process.argv[2];
if (!file) { console.error('用法: node scripts/apply-sticker-notes.mjs <notes.json>'); process.exit(1); }

const raw = JSON.parse(fs.readFileSync(file, 'utf8'));
const notes = raw.notes && typeof raw.notes === 'object' ? raw.notes : raw;
const cfgText = fs.readFileSync(path.join(ROOT, 'config.toml'), 'utf8');
const token = (cfgText.match(/^consoleToken\s*=\s*"([^"]+)"/m) || [])[1];
if (!token) throw new Error('config.toml 缺 consoleToken');

const stickers = JSON.parse(fs.readFileSync(path.join(ROOT, 'state/stickers.json'), 'utf8'));
const tagsById = new Map(stickers.map((s) => [String(s.id), Array.isArray(s.tags) ? s.tags : []]));

let ok = 0, failed = 0;
for (const [id, note] of Object.entries(notes)) {
  const text = String(note || '').trim();
  if (!text) { failed++; continue; }
  try {
    const resp = await fetch('http://127.0.0.1:3100/internal/stickers/note', {
      method: 'POST',
      headers: { 'x-control-token': token, 'content-type': 'application/json' },
      body: JSON.stringify({ id, localNote: text.slice(0, 200), tags: tagsById.get(id) || [] })
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    ok++;
  } catch (error) {
    failed++;
    console.log(`  ✗ ${String(id).slice(-12)}: ${error.message}`);
  }
  await new Promise((r) => setTimeout(r, 40));
}
console.log(`写回完成：成功 ${ok}，失败 ${failed}`);
