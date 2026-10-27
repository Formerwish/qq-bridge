import fs from 'node:fs';

const rows = fs.readFileSync('E:/qq-bridge/state/token-usage.jsonl', 'utf8')
  .trim().split('\n').map((l) => { try { return JSON.parse(l); } catch { return null; } })
  .filter(Boolean).filter((r) => r.k && (r.k === 'turn' || r.k === 'delta'));
const now = Date.now();
const H = 3600000;

function agg(list) {
  const a = { hit: 0, miss: 0, out: 0, steps: 0, turns: new Set(), keys: {} };
  for (const r of list) {
    const b = r.b || {};
    const h = b.cacheHit || 0;
    const m = (b.cacheMiss || 0) + (b.cacheWrite || 0);
    const o = b.output || 0;
    a.hit += h; a.miss += m; a.out += o; a.steps++;
    if (r.turn) a.turns.add(r.turn);
    const k = r.key || '?';
    const x = a.keys[k] = a.keys[k] || { hit: 0, miss: 0, out: 0, steps: 0, turns: new Set() };
    x.hit += h; x.miss += m; x.out += o; x.steps++;
    if (r.turn) x.turns.add(r.turn);
  }
  a.tokens = a.hit + a.miss + a.out;
  a.turnCount = a.turns.size;
  for (const x of Object.values(a.keys)) {
    x.tokens = x.hit + x.miss + x.out;
    x.turnCount = x.turns.size;
  }
  return a;
}

const day = agg(rows.filter((r) => r.t >= now - 24 * H));
console.log('24h tokens', day.tokens, 'hit', day.hit, 'miss', day.miss, 'out', day.out, 'steps', day.steps, 'turns', day.turnCount);
for (const [k, v] of Object.entries(day.keys).sort((x, y) => y[1].tokens - x[1].tokens)) {
  console.log(k, 'tokens', v.tokens, 'steps', v.steps, 'turns', v.turnCount, 'avg/step', Math.round(v.tokens / v.steps));
}
const three = agg(rows.filter((r) => r.t >= now - 3 * H));
console.log('3h tokens', three.tokens, 'steps', three.steps, 'turns', three.turnCount, 'avg/step', Math.round(three.tokens / three.steps));
