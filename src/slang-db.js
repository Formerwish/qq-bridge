// 黑话库（MySQL）存储层 —— 桥接侧读写。
//
// 与 kb-mysql（只读知识库）不同：黑话是**读写**的（学习器/工具/控制台都会写），
// 所以这里负责把内存里的 slangEntries 与 kb_slang 表对账。
//
// 设计要点：
// - **DB 是权威存储**，state/slang.json 退化为本地镜像/离线兜底（bridge 仍会写它）。
// - 用 `updated_ms`（epoch 毫秒）做「谁更新得晚谁赢」的比较：
//   桥接在内存里改完立刻写库；管理端（E:\qq-kb-admin）改完也会刷新 updated_ms，
//   两边都用这一个字段判断新旧，**避免互相覆盖**。
// - 对账是「全量 diff」：INSERT 缺的、UPDATE 更新的、DELETE 已删的。
//   删除有保护：本地刚写入（protectIds）或库里这条比我们新 → 不删，交给下次 refresh。
// - 任何数据库异常都 fail-open：本地 JSON 镜像照常工作，日志节流。
//
// 表结构见 docs/guides/KNOWLEDGE_BASE.md（kb_slang / kb_slang_revision）。

import { createPool } from 'mysql2/promise';
import { normalizeSlangEntry, SLANG_STATUS } from './slang-learner.js';

const MAX_ROWS = 2000;

export function isSlangStoreEnabled(rawCfg) {
  if (rawCfg === false) return false; // 允许直接写 slang.store: false 关掉
  return !(rawCfg && rawCfg.enabled === false);
}

function parseJsonArray(text) {
  if (!text) return [];
  try {
    const value = JSON.parse(text);
    return Array.isArray(value) ? value : [];
  } catch {
    return [];
  }
}

/** 数据库行 → 内存条目（字段名与 slang.json 保持一致）。 */
export function slangRowToEntry(row) {
  if (!row) return null;
  return normalizeSlangEntry({
    id: String(row.id ?? ''),
    content: String(row.content ?? ''),
    meaning: String(row.meaning ?? ''),
    usage: String(row.usage ?? ''),
    example: String(row.example ?? ''),
    risk: String(row.risk ?? ''),
    status: row.status,
    source: row.source,
    count: Number(row.count) || 0,
    sources: parseJsonArray(row.sources_json),
    evidence: parseJsonArray(row.evidence_json),
    lastInferenceCount: Number(row.last_inference_count) || 0,
    createdAt: new Date(Number(row.created_ms) || Date.now()).toISOString(),
    updatedAt: new Date(Number(row.updated_ms) || Number(row.created_ms) || Date.now()).toISOString()
  });
}

/** 内存条目 → 参数数组（顺序与 SQL 占位符一致）。 */
export function slangEntryToParams(entry) {
  const e = normalizeSlangEntry(entry);
  const createdMs = Date.parse(e.createdAt) || Date.now();
  const updatedMs = Date.parse(e.updatedAt) || createdMs;
  return [
    e.id,
    e.content,
    e.meaning,
    e.usage,
    e.example,
    e.risk,
    e.status,
    e.source,
    e.count,
    JSON.stringify(e.sources ?? []),
    JSON.stringify(e.evidence ?? []),
    e.lastInferenceCount,
    createdMs,
    Math.max(updatedMs, createdMs)
  ];
}

const UPSERT_SQL = `INSERT INTO kb_slang
  (id, content, meaning, \`usage\`, example, risk, status, source, count, sources_json, evidence_json, last_inference_count, created_ms, updated_ms)
  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  ON DUPLICATE KEY UPDATE
    content = VALUES(content), meaning = VALUES(meaning), \`usage\` = VALUES(\`usage\`), example = VALUES(example),
    risk = VALUES(risk), status = VALUES(status), source = VALUES(source), count = VALUES(count),
    sources_json = VALUES(sources_json), evidence_json = VALUES(evidence_json),
    last_inference_count = VALUES(last_inference_count), updated_ms = GREATEST(updated_ms, VALUES(updated_ms))`;

/**
 * @param rawMysqlCfg 复用 config.json 里 kb.mysql 的连接参数（同一个库）
 */
export function createSlangDb(rawMysqlCfg, { rawSlangCfg, log = () => {}, poolFactory } = {}) {
  const cfg = rawMysqlCfg && typeof rawMysqlCfg === 'object' ? rawMysqlCfg : {};
  const enabled = isSlangStoreEnabled(rawSlangCfg);
  let pool = null;
  let closed = false;
  let lastError = '';
  let lastErrorAt = 0;

  function noteError(where, error) {
    lastError = `${where}: ${error?.message ?? error}`;
    const now = Date.now();
    if (now - lastErrorAt > 60000) {
      lastErrorAt = now;
      log(`[slang-db] ${lastError}`);
    }
  }

  function getPool() {
    if (pool || closed || !enabled) return pool;
    try {
      if (typeof poolFactory === 'function') {
        pool = poolFactory(cfg);
      } else {
        pool = createPool({
          host: cfg.host || '127.0.0.1',
          port: Number(cfg.port) || 3306,
          user: cfg.user || '',
          password: cfg.password || '',
          database: cfg.database || 'qq_bridge_kb',
          waitForConnections: true,
          connectionLimit: Math.max(1, Math.min(4, Number(cfg.connectionLimit) || 2)),
          connectTimeout: Math.max(500, Number(cfg.connectTimeoutMs) || 3000),
          charset: 'utf8mb4',
          multipleStatements: false
        });
      }
    } catch (error) {
      noteError('创建连接池失败', error);
      pool = null;
    }
    return pool;
  }

  async function query(sql, params) {
    const p = getPool();
    if (!p) return null;
    try {
      const [rows] = await p.query({ sql, timeout: 5000 }, params);
      return rows;
    } catch (error) {
      noteError('查询失败', error);
      return null;
    }
  }

  /** 读全库（上限 2000，按最近更新排序）。 */
  async function loadAll() {
    if (!enabled) return { ok: false, entries: [], rows: [] };
    const rows = await query(
      `SELECT id, content, meaning, \`usage\`, example, risk, status, source, count,
              sources_json, evidence_json, last_inference_count, created_ms, updated_ms
       FROM kb_slang ORDER BY updated_ms DESC LIMIT ${MAX_ROWS}`
    );
    if (rows === null) return { ok: false, entries: [], rows: [] };
    return {
      ok: true,
      rows,
      entries: rows.map(slangRowToEntry).filter((e) => e && e.content)
    };
  }

  /**
   * 全量对账：内存 → 数据库。
   * @param entries 内存条目
   * @param opts.protectIds 本地刚写入、不许被「删除」清掉的 id
   */
  async function sync(entries, { protectIds } = {}) {
    if (!enabled) return { ok: false, skipped: true };
    const list = (Array.isArray(entries) ? entries : []).map(normalizeSlangEntry).filter((e) => e?.content);
    const rows = await query('SELECT id, content, updated_ms FROM kb_slang LIMIT 5000');
    if (rows === null) return { ok: false, skipped: true };

    const byId = new Map();
    const byContent = new Map();
    for (const row of rows) {
      byId.set(String(row.id), Number(row.updated_ms) || 0);
      byContent.set(String(row.content), { id: String(row.id), updatedMs: Number(row.updated_ms) || 0 });
    }

    let inserted = 0;
    let updated = 0;
    let skippedNewer = 0;
    for (const entry of list) {
      const params = slangEntryToParams(entry);
      const updatedMs = params[params.length - 1];
      const existing = byId.get(entry.id) ?? byContent.get(entry.content)?.updatedMs;
      if (existing === undefined) {
        const res = await query(UPSERT_SQL, params);
        if (res !== null) inserted++;
        continue;
      }
      if (existing <= updatedMs) {
        const res = await query(UPSERT_SQL, params);
        if (res !== null) updated++;
      } else {
        skippedNewer++; // 库里更新（通常是管理端刚改过）→ 不覆盖，等 refresh 拉回来
      }
    }

    // 删除：内存里没有、库里还留着 → 删（保护刚写入的 id，避免误删未落库的新条目）
    const keep = new Set(list.map((e) => e.id));
    const guard = protectIds instanceof Set ? protectIds : new Set();
    let deleted = 0;
    for (const row of rows) {
      const id = String(row.id);
      if (keep.has(id) || guard.has(id)) continue;
      const res = await query('DELETE FROM kb_slang WHERE id = ?', [id]);
      if (res !== null) deleted++;
    }
    return { ok: true, inserted, updated, deleted, skippedNewer, total: rows.length };
  }

  /** 批量写入（导入/恢复用，按 updated_ms 取大值，不会把新数据写旧）。 */
  async function replaceAll(entries) {
    if (!enabled) return { ok: false, skipped: true, count: 0 };
    const list = (Array.isArray(entries) ? entries : []).map(normalizeSlangEntry).filter((e) => e?.content);
    let count = 0;
    for (const entry of list) {
      const res = await query(UPSERT_SQL, slangEntryToParams(entry));
      if (res !== null) count++;
    }
    return { ok: true, count };
  }

  async function stats() {
    if (!enabled) return { enabled: false, ok: false };
    const rows = await query(
      'SELECT COUNT(*) AS total, SUM(status = \'confirmed\') AS confirmed, SUM(status = \'candidate\') AS candidates, SUM(status = \'rejected\') AS rejected, MAX(updated_at) AS latest FROM kb_slang'
    );
    const row = Array.isArray(rows) ? rows[0] : null;
    return {
      enabled: true,
      ok: Boolean(row),
      total: Number(row?.total) || 0,
      confirmed: Number(row?.confirmed) || 0,
      candidates: Number(row?.candidates) || 0,
      rejected: Number(row?.rejected) || 0,
      latest: row?.latest instanceof Date ? row.latest.toISOString() : (row?.latest ?? null),
      lastError: lastError || null
    };
  }

  function close() {
    closed = true;
    try { pool?.end?.(); } catch {}
    pool = null;
  }

  return { enabled, loadAll, sync, replaceAll, stats, close };
}

export { SLANG_STATUS };
