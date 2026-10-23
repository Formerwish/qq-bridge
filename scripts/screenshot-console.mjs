// 用本机 Chrome（puppeteer-core，无下载）给控制台页面截图，便于检查排版。
// 用法：node scripts/screenshot-console.mjs [page ...]
// 生成：state/screenshots/<name>.png
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import puppeteer from 'puppeteer-core';
import { fileURLToPath } from 'node:url';

const ROOT = fileURLToPath(new URL('..', import.meta.url));
const OUT = path.join(ROOT, 'state/screenshots');
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const BASE = process.env.QQ_CONSOLE_URL || 'http://127.0.0.1:21001';

function mintToken() {
  const secret = fs.readFileSync(path.join(ROOT, 'state/web-secret'), 'utf8').trim();
  const b64 = (obj) => Buffer.from(JSON.stringify(obj)).toString('base64url');
  const now = Math.floor(Date.now() / 1000);
  const header = b64({ alg: 'HS256', typ: 'JWT' });
  const payload = b64({ sub: '1', name: 'admin', role: 'admin', csrf: 'screenshot', iat: now, exp: now + 3600 });
  const sig = crypto.createHmac('sha256', secret).update(`${header}.${payload}`).digest('base64url');
  return `${header}.${payload}.${sig}`;
}

const pages = process.argv.slice(2).filter((a) => !a.startsWith('--'));
const targets = pages.length
  ? pages.map((p) => ({ name: p.replace(/[^a-z0-9]+/gi, '-').replace(/^-|-$/g, '') || 'root', url: BASE + p, anonymous: p === '/login' }))
  : [
      { name: 'dashboard', url: BASE + '/' },
      { name: 'sessions', url: BASE + '/sessions' },
      { name: 'periods', url: BASE + '/periods' },
      { name: 'kb', url: BASE + '/kb' },
      { name: 'stickers', url: BASE + '/stickers' },
      { name: 'tools', url: BASE + '/tools' },
      { name: 'tokens', url: BASE + '/tokens' },
      { name: 'login', url: BASE + '/login', anonymous: true }
    ];

fs.mkdirSync(OUT, { recursive: true });
const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: 'new',
  args: ['--disable-gpu', '--no-sandbox', '--hide-scrollbars']
});
const token = mintToken();
for (const target of targets) {
  const context = target.anonymous ? await browser.createBrowserContext() : browser.defaultBrowserContext();
  const page = await context.newPage();
  await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 });
  if (!target.anonymous) {
    await page.setCookie({ name: 'qq_console', value: token, domain: '127.0.0.1', path: '/', httpOnly: true });
  }
  try {
    await page.goto(target.url, { waitUntil: 'networkidle2', timeout: 30000 });
    await new Promise((r) => setTimeout(r, 500));
    const file = path.join(OUT, `${target.name}.png`);
    await page.screenshot({ path: file, fullPage: !process.argv.includes('--viewport') });
    const title = await page.title();
    console.log(`✓ ${target.name}: ${file} (${title})`);
  } catch (error) {
    console.log(`✗ ${target.name}: ${error.message}`);
  }
  await page.close();
  if (target.anonymous) await context.close();
}
await browser.close();
