import fs from 'node:fs';
import zlib from 'node:zlib';
import path from 'node:path';

const sid = 'session-e3d58c77-ef81-4f26-8197-5f8102d8da88';
const dir = path.join(process.env.USERPROFILE, '.dsh/sessions/--E-qq-bridge-state-agents--', sid);
const file = fs.readdirSync(dir, { recursive: true }).find((f) => String(f).endsWith('session.v4.jsonl.zstd'));
const raw = zlib.zstdDecompressSync(fs.readFileSync(path.join(dir, String(file)))).toString('utf8');
for (const line of raw.split('\n')) {
  if (!line.includes('"request/header"')) continue;
  const o = JSON.parse(line);
  const tools = o.data?.header?.tools || [];
  const chars = JSON.stringify(tools).length;
  console.log('tools', tools.length, 'json chars', chars, 'approx tokens', Math.round(chars / 2.5));
  const sorted = tools.map((t) => [t.name, JSON.stringify(t).length]).sort((a, b) => b[1] - a[1]).slice(0, 10);
  console.log(sorted.map(([n, c]) => `${n}:${c}`).join(' | '));
  break;
}
