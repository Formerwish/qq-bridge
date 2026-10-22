// 直接以 stdio 启动 MCP server，验证 qq_admin_config 已注册且能改配置（不依赖 DSH 是否重启）。
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import fs from 'node:fs';

process.env.QQ_BRIDGE_CONFIG_DIR = process.env.QQ_BRIDGE_CONFIG_DIR || 'E:/qq-bridge';

const transport = new StdioClientTransport({
  command: process.execPath,
  args: ['E:/qq-bridge/src/mcp-snowluma-safe.js'],
  cwd: 'E:/qq-bridge',
  stderr: 'pipe'
});
const client = new Client({ name: 'admin-config-probe', version: '1.0.0' }, { capabilities: {} });
await client.connect(transport);

const tools = await client.listTools();
const names = tools.tools.map((t) => t.name);
console.log('admin_config 已注册:', names.includes('qq_admin_config'));
console.log('工具数:', names.length);

const state = JSON.parse(fs.readFileSync('E:/qq-bridge/state/social-v2.json', 'utf8'));
const key = 'private:583937437';
const token = state.conversations?.[key]?.agentToken || state.conversations?.get?.(key)?.agentToken;
const result = await client.callTool({
  name: 'qq_admin_config',
  arguments: { key, token, action: 'get' }
});
const text = (result.content || []).map((c) => c.text || '').join('\n');
console.log('调用 get 返回:', text.slice(0, 200).replace(/\n/g, ' '));
await client.close();
