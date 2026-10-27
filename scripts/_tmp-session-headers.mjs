import fs from 'node:fs';
import zlib from 'node:zlib';
import path from 'node:path';

const sid = 'session-e3d58c77-ef81-4f26-8197-5f8102d8da88';
const dir = path.join(process.env.USERPROFILE, '.dsh/sessions/--E-qq-bridge-state-agents--', sid);
const file = fs.readdirSync(dir, { recursive: true }).find((f) => String(f).endsWith('session.v4.jsonl.zstd'));
const raw = zlib.zstdDecompressSync(fs.readFileSync(path.join(dir, String(file)))).toString('utf8');
const lines = raw.split('\n').filter(Boolean);
let shown = 0;
for (const line of lines) {
  if (!/request\/header|request\/context|compaction\/summary|model\/selection/.test(line)) continue;
  if (shown++ > 8) break;
  try {
    const o = JSON.parse(line);
    const s = JSON.stringify(o).slice(0, 600);
    console.log(s);
  } catch {}
}
