import fs from 'node:fs';
import zlib from 'node:zlib';
import path from 'node:path';

const sid = 'session-e3d58c77-ef81-4f26-8197-5f8102d8da88';
const dir = path.join(process.env.USERPROFILE, '.dsh/sessions/--E-qq-bridge-state-agents--', sid);
const file = fs.readdirSync(dir, { recursive: true }).find((f) => String(f).endsWith('session.v4.jsonl.zstd'));
const raw = zlib.zstdDecompressSync(fs.readFileSync(path.join(dir, String(file)))).toString('utf8');
const sizes = [];
for (const line of raw.split('\n')) {
  if (!line.includes('"user/message"')) continue;
  try {
    const o = JSON.parse(line);
    const msg = o.data?.message || o.data || {};
    const text = JSON.stringify(msg.content ?? msg.text ?? msg);
    sizes.push(text.length);
  } catch {}
}
sizes.sort((a, b) => b - a);
const sum = sizes.reduce((a, b) => a + b, 0);
console.log('user messages', sizes.length, 'total chars', sum, 'avg', Math.round(sum / sizes.length), 'top10', sizes.slice(0, 10));
