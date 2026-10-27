import fs from 'node:fs';
import zlib from 'node:zlib';
import path from 'node:path';

const base = path.join(process.env.USERPROFILE, '.dsh/sessions/--E-qq-bridge-state-agents--');
const sessions = JSON.parse(fs.readFileSync('E:/qq-bridge/state/sessions.json', 'utf8')).sessions;
const rows = [];
for (const [key, sid] of Object.entries(sessions)) {
  const dir = path.join(base, sid);
  const file = fs.readdirSync(dir, { recursive: true }).find((f) => String(f).endsWith('session.v4.jsonl.zstd'));
  if (!file) continue;
  const p = path.join(dir, String(file));
  const raw = zlib.zstdDecompressSync(fs.readFileSync(p)).toString('utf8');
  const lines = raw.split('\n').filter(Boolean);
  let chars = 0;
  const roles = {};
  let maxLine = 0;
  for (const line of lines) {
    chars += line.length;
    maxLine = Math.max(maxLine, line.length);
    try {
      const obj = JSON.parse(line);
      const role = obj?.event?.message?.role || obj?.event?.payload?.role || obj?.role || obj?.type || '?';
      roles[role] = (roles[role] || 0) + 1;
    } catch {}
  }
  rows.push({ key, sid: sid.slice(0, 20), compMB: +(fs.statSync(p).size / 1048576).toFixed(2), uncompMB: +(raw.length / 1048576).toFixed(2), lines: lines.length, chars, approxTokens: Math.round(chars / 3.2), maxLine, roles });
}
rows.sort((a, b) => b.uncompMB - a.uncompMB);
for (const r of rows) console.log(JSON.stringify(r));
