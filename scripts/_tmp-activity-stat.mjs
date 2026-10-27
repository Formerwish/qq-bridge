import fs from 'node:fs';
const lines = fs.readFileSync('E:/qq-bridge/state/qq-activity.log', 'utf8').split('\n');
let out = 0, send = 0, inbox = 0, wake = 0;
for (const l of lines) {
  if (!/^\[\d\d:\d\d:\d\d\]/.test(l)) continue;
  if (l.includes('AI 内部输出')) out++;
  else if (l.includes('[send]') && l.includes('成功')) send++;
  else if (l.includes('消息已入未读')) inbox++;
  if (l.includes('计划唤醒')) wake++;
}
console.log('AI内部输出(未发言回合)', out, '| send成功', send, '| 未读消息', inbox, '| 计划唤醒', wake);
