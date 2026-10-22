// 控制台地址解析（consoleUrl / consolePort）离线单测 + 通配监听可达性验证。
//
// 覆盖：
// - consoleUrl 优先，consolePort 兼容；0.0.0.0/:: 监听但客户端地址映射为 127.0.0.1
// - https 默认 443、非法 URL 退回只监听本机并给出 warning
// - 真实 listen(0.0.0.0) 之后从 127.0.0.1 能连上（通配地址不等于可连接地址）
//
// 运行：node scripts/test-console-endpoint.mjs

import assert from 'node:assert/strict';
import http from 'node:http';
import { resolveConsoleEndpoint, isWildcardHost } from '../src/console-endpoint.js';

let passed = 0;
function test(name, fn) {
  try {
    fn();
    passed++;
    console.log(`  ✓ ${name}`);
  } catch (error) {
    console.error(`  ✗ ${name}\n    ${error?.message ?? error}`);
    process.exitCode = 1;
  }
}
async function testAsync(name, fn) {
  try {
    await fn();
    passed++;
    console.log(`  ✓ ${name}`);
  } catch (error) {
    console.error(`  ✗ ${name}\n    ${error?.message ?? error}`);
    process.exitCode = 1;
  }
}

console.log('console-endpoint 单测：');

test('没有配置：127.0.0.1:3100', () => {
  const ep = resolveConsoleEndpoint({});
  assert.equal(ep.listenHost, '127.0.0.1');
  assert.equal(ep.port, 3100);
  assert.equal(ep.clientUrl, 'http://127.0.0.1:3100');
  assert.equal(ep.wildcard, false);
});

test('consoleUrl 监听 0.0.0.0：客户端地址映射到 127.0.0.1', () => {
  const ep = resolveConsoleEndpoint({ consoleUrl: 'http://0.0.0.0:3100' });
  assert.equal(ep.source, 'url');
  assert.equal(ep.listenHost, '0.0.0.0');
  assert.equal(ep.clientUrl, 'http://127.0.0.1:3100');
  assert.equal(ep.publicUrl, 'http://0.0.0.0:3100');
  assert.equal(ep.wildcard, true);
});

test('IPv6 通配 [::]：监听 ::，客户端仍走 127.0.0.1', () => {
  const ep = resolveConsoleEndpoint({ consoleUrl: 'http://[::]:3100' });
  assert.equal(ep.listenHost, '::');
  assert.equal(ep.clientUrl, 'http://127.0.0.1:3100');
  assert.equal(ep.wildcard, true);
});

test('指定具体主机：监听与客户端一致', () => {
  const ep = resolveConsoleEndpoint({ consoleUrl: 'http://192.168.1.5:3200' });
  assert.equal(ep.listenHost, '192.168.1.5');
  assert.equal(ep.port, 3200);
  assert.equal(ep.clientUrl, 'http://192.168.1.5:3200');
  assert.equal(ep.wildcard, false);
});

test('https 未写端口 → 443', () => {
  const ep = resolveConsoleEndpoint({ consoleUrl: 'https://kb.example.com' });
  assert.equal(ep.port, 443);
  assert.equal(ep.clientUrl, 'https://kb.example.com:443');
});

test('consoleUrl 优先于 consolePort', () => {
  const ep = resolveConsoleEndpoint({ consoleUrl: 'http://0.0.0.0:4000', consolePort: 3100 });
  assert.equal(ep.port, 4000);
  assert.equal(ep.source, 'url');
});

test('非法 consoleUrl：退回 127.0.0.1 + consolePort，并带 warning', () => {
  const ep = resolveConsoleEndpoint({ consoleUrl: 'not-a-url', consolePort: 3200 });
  assert.equal(ep.listenHost, '127.0.0.1');
  assert.equal(ep.port, 3200);
  assert.equal(ep.wildcard, false);
  assert.equal(ep.warnings.length, 1);
});

test('consolePort: 0（测试用）保留 0，不夹成 3100', () => {
  const ep = resolveConsoleEndpoint({ consolePort: 0 });
  assert.equal(ep.port, 0);
  assert.equal(ep.listenHost, '127.0.0.1');
});

test('非法 consolePort：回落 3100 并 warning', () => {
  const ep = resolveConsoleEndpoint({ consolePort: 99999 });
  assert.equal(ep.port, 3100);
  assert.equal(ep.warnings.length, 1);
});

test('isWildcardHost 识别常见通配写法', () => {
  for (const h of ['0.0.0.0', '::', '[::]', '*', '']) assert.equal(isWildcardHost(h), true, h);
  for (const h of ['127.0.0.1', '192.168.1.5', 'kb.example.com']) assert.equal(isWildcardHost(h), false, h);
});

await testAsync('真实 listen(0.0.0.0) 后能从 127.0.0.1 连上（通配 ≠ 可连接）', async () => {
  const ep = resolveConsoleEndpoint({ consoleUrl: 'http://0.0.0.0:0' });
  const server = http.createServer((_req, res) => { res.end('ok'); });
  await new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(ep.port, ep.listenHost, resolve);
  });
  const { port, address } = server.address();
  assert.ok(address === '0.0.0.0' || address === '::', `监听地址应通配，实际 ${address}`);
  const text = await new Promise((resolve, reject) => {
    http.get(`http://127.0.0.1:${port}/`, (res) => {
      let buf = '';
      res.on('data', (c) => { buf += c; });
      res.on('end', () => resolve(buf));
    }).on('error', reject);
  });
  assert.equal(text, 'ok');
  await new Promise((resolve) => server.close(resolve));
});

console.log(`\n通过 ${passed} 项。`);
