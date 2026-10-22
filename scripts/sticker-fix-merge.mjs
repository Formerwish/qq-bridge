// 合并 state/sticker-fix/out-*.json → state/sticker-fix-merged.json（{"notes":{id:note}}）
import fs from 'node:fs';
import path from 'node:path';

const dir = 'E:/qq-bridge/state/sticker-fix';
const files = fs.readdirSync(dir).filter((f) => /^out-\d+\.json$/.test(f)).sort();
const notes = {};
for (const file of files) {
  const data = JSON.parse(fs.readFileSync(path.join(dir, file), 'utf8'));
  for (const item of data.notes || []) {
    if (item?.id && item?.note) notes[item.id] = item.note.trim();
  }
}
const out = 'E:/qq-bridge/state/sticker-fix-merged.json';
fs.writeFileSync(out, JSON.stringify({ notes }, null, 2), 'utf8');
console.log(`合并 ${files.length} 个文件，${Object.keys(notes).length} 条 -> ${out}`);
