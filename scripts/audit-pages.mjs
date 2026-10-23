// 逐页审查：HTTP/控制台错误、横向溢出、超出视口的元素、空内容、按钮/输入数量。
// 用法：node scripts/audit-pages.mjs [--shots]
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import puppeteer from 'puppeteer-core';
import { fileURLToPath } from 'node:url';

const ROOT = fileURLToPath(new URL('..', import.meta.url));
const BASE = process.env.QQ_CONSOLE_URL || 'http://127.0.0.1:21001';
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const shots = process.argv.includes('--shots');
const OUT = path.join(ROOT, 'state/screenshots/audit');
fs.mkdirSync(OUT, { recursive: true });

function mint() {
  const secret = fs.readFileSync(path.join(ROOT, 'state/web-secret'), 'utf8').trim();
  const b64 = (o) => Buffer.from(JSON.stringify(o)).toString('base64url');
  const now = Math.floor(Date.now() / 1000);
  const h = b64({ alg: 'HS256', typ: 'JWT' });
  const p = b64({ sub: '1', name: 'admin', role: 'admin', csrf: 'audit', iat: now, exp: now + 3600 });
  return `${h}.${p}.` + crypto.createHmac('sha256', secret).update(`${h}.${p}`).digest('base64url');
}

const pages = [
  ['/', 'dashboard'],
  ['/sessions', 'sessions'],
  ['/sessions?key=group:123456789', 'session-group'],
  ['/sessions?key=private:123456789', 'session-private'],
  ['/periods', 'periods'],
  ['/kb', 'kb'],
  ['/slang', 'slang'],
  ['/tools', 'tools'],
  ['/logs', 'logs'],
  ['/stickers', 'stickers'],
  ['/roles', 'roles'],
  ['/presets', 'presets'],
  ['/tokens', 'tokens'],
  ['/users', 'users'],
  ['/settings', 'settings'],
  ['/login', 'login', true]
];

const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new', args: ['--no-sandbox', '--hide-scrollbars'] });
const token = mint();
const results = [];

for (const [urlPath, name, anonymous] of pages) {
  const context = anonymous ? await browser.createBrowserContext() : browser.defaultBrowserContext();
  const page = await context.newPage();
  await page.setViewport({ width: 1440, height: 900 });
  if (!anonymous) await page.setCookie({ name: 'qq_console', value: token, domain: '127.0.0.1', path: '/' });
  const errors = [];
  page.on('pageerror', (e) => errors.push('pageerror: ' + e.message));
  page.on('console', (msg) => { if (msg.type() === 'error') errors.push('console: ' + msg.text().slice(0, 160)); });
  let status = 0;
  try {
    const resp = await page.goto(BASE + urlPath, { waitUntil: 'networkidle2', timeout: 30000 });
    status = resp?.status() || 0;
    await new Promise((r) => setTimeout(r, 400));
    const info = await page.evaluate(() => {
      const doc = document.documentElement;
      const overflow = doc.scrollWidth - doc.clientWidth;
      const bad = [];
      document.querySelectorAll('body *').forEach((el) => {
        const r = el.getBoundingClientRect();
        if (r.width > 0 && (r.right > window.innerWidth + 2 || r.left < -2)) {
          const tag = el.tagName.toLowerCase();
          if (bad.length < 5 && !['html', 'body'].includes(tag)) {
            bad.push(`${tag}.${(el.className || '').toString().split(' ')[0]} right=${Math.round(r.right)}`);
          }
        }
      });
      const text = (document.querySelector('main')?.innerText || '').trim();
      return {
        title: document.title,
        overflow,
        bad,
        chars: text.length,
        buttons: document.querySelectorAll('.btn').length,
        inputs: document.querySelectorAll('input, select, textarea').length,
        tables: document.querySelectorAll('table').length,
        empty: /暂无|没有|桥接离线|不可达/.test(text)
      };
    });
    if (shots) await page.screenshot({ path: path.join(OUT, `${name}.png`), fullPage: false });
    results.push({ name, urlPath, status, ...info, errors });
  } catch (error) {
    results.push({ name, urlPath, status, error: error.message, errors });
  }
  await page.close();
  if (anonymous) await context.close();
}
await browser.close();

for (const r of results) {
  const flags = [];
  if (r.status !== 200 && !(r.name === 'dashboard' && r.status === 200)) flags.push('HTTP' + r.status);
  if (r.overflow > 1) flags.push('横向溢出' + r.overflow + 'px');
  if (r.bad?.length) flags.push('越界元素:' + r.bad.join('; '));
  if (r.empty) flags.push('疑似空状态');
  if (r.errors?.length) flags.push('JS错误:' + r.errors.join(' | '));
  console.log(`${r.name.padEnd(16)} ${String(r.status).padEnd(4)} chars=${String(r.chars ?? '-').padEnd(6)} btn=${String(r.buttons ?? '-').padEnd(3)} in=${String(r.inputs ?? '-').padEnd(3)} ${flags.length ? '⚠ ' + flags.join(' / ') : 'ok'}`);
}
fs.writeFileSync(path.join(OUT, 'summary.json'), JSON.stringify(results, null, 2), 'utf8');
