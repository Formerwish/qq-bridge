// 配置读写：config.toml 是唯一权威文件，config.json 只是**过渡期生成的镜像**。
//
// 为什么需要这一层：
// - 配置项被 bridge / MCP / 40+ 脚本读取，直接散落 `JSON.parse(fs.readFileSync('config.json'))`
//   无法从 JSON 平滑迁到 TOML。统一入口后，迁移只改这一处，调用方无感。
// - 程序化保存（token 自愈、控制台改设置）要同时更新 TOML 与 JSON 镜像，否则两边不一致。
// - TOML 没有 null：序列化前要剔除 null/undefined，否则 smol-toml 直接抛错。
//
// 迁移策略（P0）：
//   1) `config.toml` 存在 → 一律读它（source='toml'）；
//   2) 只有 `config.json` → 兼容读 JSON 并告警（一次性迁移用）；
//   3) 保存时永远写 TOML，并按需生成 JSON 镜像（`mirrorJson`），供尚未迁移的脚本读取；
//   4) P6 删除镜像生成，全仓切换完成后 JSON 即可删除。
//
// 注意：TOML 序列化会丢弃注释（格式限制）。程序化保存只应发生在值真的变化时；
// 用户手写的注释在"程序保存"后会丢，这一点写进部署文档。

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse as parseToml, stringify as stringifyToml } from 'smol-toml';

const MODULE_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
let rootOverride = null;

/** 测试/多实例可覆盖配置根目录（默认是仓库根）。 */
export function setConfigRoot(dir) {
  rootOverride = dir ? path.resolve(dir) : null;
}
export function configRoot() {
  return rootOverride ?? MODULE_ROOT;
}
export const ROOT = MODULE_ROOT;
export const CONFIG_TOML = path.join(MODULE_ROOT, 'config.toml');
export const CONFIG_JSON = path.join(MODULE_ROOT, 'config.json');
export function configTomlPath() { return path.join(configRoot(), 'config.toml'); }
export function configJsonPath() { return path.join(configRoot(), 'config.json'); }

const TOML_HEADER = [
  '# qq-bridge 配置（TOML）',
  '#',
  '# 说明：',
  '#   - 这是唯一权威配置文件；程序保存（如 token 自愈、控制台改设置）会重新序列化本文件，',
  '#     手写注释可能丢失，重要说明请写进 docs 或 README。',
  '#   - 桥接启动时读取；标了「热重载」的项可在控制台/管理员工具里改完即时生效。',
  '#   - 各字段含义见 docs/guides/CONFIG.md（部署文档）。',
  ''
].join('\n');

/** 当前应读取的配置文件：TOML 优先，JSON 兜底。 */
export function configPath() {
  const toml = configTomlPath();
  const json = configJsonPath();
  if (fs.existsSync(toml)) return toml;
  if (fs.existsSync(json)) return json;
  return toml;
}

function stripBom(text) {
  return text.charCodeAt(0) === 0xfeff ? text.slice(1) : text;
}

/** 剔除 TOML 不支持的 null/undefined（递归处理表与数组）。 */
export function sanitizeForToml(value) {
  if (value === null || value === undefined) return undefined;
  if (Array.isArray(value)) {
    return value
      .map((item) => sanitizeForToml(item))
      .filter((item) => item !== undefined);
  }
  if (typeof value === 'object') {
    const out = {};
    for (const [key, item] of Object.entries(value)) {
      const next = sanitizeForToml(item);
      if (next !== undefined) out[key] = next;
    }
    return out;
  }
  if (typeof value === 'number' && !Number.isFinite(value)) return undefined;
  return value;
}

/**
 * 严格读取配置文档。
 * @returns {{ data: object, source: string, format: 'toml'|'json' }}
 */
export function loadConfigDocument(file = configPath()) {
  if (!fs.existsSync(file)) {
    throw new Error(`配置文件不存在：${file}（应先运行 scripts/migrate-config.mjs 或从 config.example.toml 复制）`);
  }
  const raw = stripBom(fs.readFileSync(file, 'utf8'));
  let data;
  try {
    data = file.endsWith('.toml') ? parseToml(raw) : JSON.parse(raw);
  } catch (error) {
    throw new Error(`配置解析失败（${file}）：${error?.message ?? error}`);
  }
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    throw new Error(`配置顶层必须是表/对象：${file}`);
  }
  return { data, source: file, format: file.endsWith('.toml') ? 'toml' : 'json' };
}

/** 宽松读取：读不到/解析失败时返回 fallback（供"只读几个字段"的老代码用）。 */
export function readConfigRaw(fallback = {}) {
  try {
    return loadConfigDocument().data;
  } catch {
    return fallback;
  }
}

export function toToml(data) {
  const body = stringifyToml(sanitizeForToml(data) ?? {});
  return TOML_HEADER + (body.endsWith('\n') ? body : `${body}\n`);
}

function writeFileAtomic(file, text) {
  const tmp = `${file}.${process.pid}.tmp`;
  fs.writeFileSync(tmp, text, { encoding: 'utf8', mode: 0o600 });
  for (let attempt = 0; attempt < 4; attempt++) {
    try {
      fs.renameSync(tmp, file);
      return;
    } catch (error) {
      if (error?.code !== 'EPERM' && error?.code !== 'EACCES' && error?.code !== 'EBUSY') throw error;
      Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 40 * (attempt + 1));
    }
  }
  // 最后兜底：直接覆盖（非原子，但至少不丢配置）。
  fs.writeFileSync(file, text, { encoding: 'utf8', mode: 0o600 });
  try { fs.unlinkSync(tmp); } catch {}
}

/**
 * 保存配置：写 TOML，并（默认）同步生成 JSON 镜像供过渡期脚本读取。
 * @returns {{ toml: string, json: string|null }}
 */
export function writeConfigDocument(data, { mirrorJson = true, jsonPath = configJsonPath() } = {}) {
  const tomlPath = configTomlPath();
  writeFileAtomic(tomlPath, toToml(data));
  let jsonWritten = null;
  if (mirrorJson) {
    writeFileAtomic(jsonPath, `${JSON.stringify(data, null, 2)}\n`);
    jsonWritten = jsonPath;
  }
  return { toml: tomlPath, json: jsonWritten };
}

/** 读 → 改 → 写（mutator 直接改传入对象或返回新对象）。 */
export function updateConfigDocument(mutator, opts) {
  const { data } = loadConfigDocument();
  const next = mutator(data) ?? data;
  writeConfigDocument(next, opts);
  return next;
}

/**
 * 把 config.toml 同步成 JSON 镜像（只在内容不同时写）。
 * 过渡期给尚未迁移的脚本用：桥接启动时跑一次，用户改完 TOML 重启即同步。
 */
export function syncConfigMirror({ jsonPath = configJsonPath() } = {}) {
  const { data } = loadConfigDocument();
  const next = `${JSON.stringify(data, null, 2)}\n`;
  let current = null;
  try {
    current = stripBom(fs.readFileSync(jsonPath, 'utf8'));
  } catch {}
  if (current === next) return { updated: false, path: jsonPath };
  writeFileAtomic(jsonPath, next);
  return { updated: true, path: jsonPath };
}
