// 控制台监听/访问地址解析（consoleUrl 优先，consolePort 向后兼容）。
//
// 为什么要拆出来：以前只有一个 `consolePort`，而监听地址写死 `127.0.0.1`。
// 现在要支持「监听 0.0.0.0 / 指定主机名」以及以后可能挂反代，所以配置侧改成 URL：
//
//   "consoleUrl": "http://0.0.0.0:3100"   → 监听 0.0.0.0:3100，本机客户端连 127.0.0.1:3100
//   "consoleUrl": "http://127.0.0.1:3100" → 只监听本机
//   "consolePort": 3100                    → 旧配置，等同 127.0.0.1:3100（继续支持）
//   "consolePort": 0                       → 测试用：系统分配端口（监听 127.0.0.1）
//
// 两个关键点：
// 1. **0.0.0.0 / :: 不能当客户端地址**（连不上的平台差异太大），所以 clientUrl 会把
//    通配地址映射成 127.0.0.1；`publicUrl` 保留用户写的原样（可能是反代域名）。
// 2. 解析失败时**不能静默退回默认端口**却监听 0.0.0.0 —— 那等于把一个管理 API 意外开放到
//    全网。所以 URL 非法时退回「127.0.0.1 + consolePort/3100」，并把 `warnings` 带出去。

const WILDCARD_HOSTS = new Set(['0.0.0.0', '::', '[::]', '*', '']);

export function isWildcardHost(hostname) {
  return WILDCARD_HOSTS.has(String(hostname ?? '').trim().toLowerCase());
}

/** 去掉 IPv6 的方括号。 */
function bareHost(host) {
  return String(host ?? '').replace(/^\[/, '').replace(/\]$/, '');
}

/**
 * @param {{consoleUrl?: string, consolePort?: number|string}} cfg
 * @returns {{source:'url'|'port', listenHost:string, port:number, clientUrl:string, publicUrl:string, wildcard:boolean, warnings:string[]}}
 */
export function resolveConsoleEndpoint(cfg = {}) {
  const warnings = [];
  const rawUrl = String(cfg?.consoleUrl ?? '').trim();
  const rawPort = cfg?.consolePort;
  const legacyPort = Number(rawPort);

  if (rawUrl) {
    try {
      const url = new URL(rawUrl);
      if (!['http:', 'https:'].includes(url.protocol)) throw new Error(`不支持的协议 ${url.protocol}`);
      const hostname = bareHost(url.hostname);
      const port = url.port ? Number(url.port) : (url.protocol === 'https:' ? 443 : 80);
      if (!Number.isInteger(port) || port < 0 || port > 65535) throw new Error(`端口不合法 ${url.port}`);
      const wildcard = isWildcardHost(hostname);
      const listenHost = wildcard ? (hostname.includes(':') ? '::' : '0.0.0.0') : hostname;
      const clientHost = wildcard ? '127.0.0.1' : hostname;
      return {
        source: 'url',
        listenHost,
        port,
        clientUrl: `${url.protocol}//${clientHost}:${port}`,
        publicUrl: rawUrl,
        wildcard,
        warnings
      };
    } catch (error) {
      warnings.push(`consoleUrl「${rawUrl}」无法解析（${error?.message ?? error}），已退回 consolePort/默认端口并只监听 127.0.0.1`);
    }
  }

  const port = Number.isFinite(legacyPort) ? legacyPort : 3100;
  if (port < 0 || port > 65535) warnings.push(`consolePort「${rawPort}」不合法，已使用 3100`);
  const safePort = port >= 0 && port <= 65535 ? port : 3100;
  return {
    source: 'port',
    listenHost: '127.0.0.1',
    port: safePort,
    clientUrl: `http://127.0.0.1:${safePort}`,
    publicUrl: `http://127.0.0.1:${safePort}`,
    wildcard: false,
    warnings
  };
}
