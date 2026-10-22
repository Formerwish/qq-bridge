import fs from 'node:fs';

const ROOT = 'E:/qq-bridge';
const cfg = fs.readFileSync(ROOT + '/config.toml', 'utf8');
const token = (cfg.match(/^consoleToken\s*=\s*"([^"]+)"/m) || [])[1];
const state = JSON.parse(fs.readFileSync(ROOT + '/state/social-v2.json', 'utf8'));
const agent = state.conversations['group:2157035230'].agentToken;
const id = '1900806455_0_0_0_5CE12D5FCF9549A13890B70ABCD65BEA_0_0';
const resp = await fetch('http://127.0.0.1:3100/api/socialV2/sticker-note', {
  method: 'POST',
  headers: { 'x-console-token': token, 'x-agent-token': agent, 'x-agent-call': '1', 'content-type': 'application/json' },
  body: JSON.stringify({ key: 'group:2157035230', stickerId: id, note: '大拇指朝下，摆出一副无语，否定的表情' })
});
const data = await resp.json();
console.log('restore ok:', data.ok, '| note:', data.sticker?.localNote);
