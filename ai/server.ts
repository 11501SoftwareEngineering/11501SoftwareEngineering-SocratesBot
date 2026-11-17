import { createChatService } from './service.ts';

const port = Number(process.env.CHAT_API_PORT || 8008);
if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error('CHAT_API_PORT 必須介於 1024–65535。');
const origins = (process.env.CHAT_ALLOWED_ORIGINS || 'http://127.0.0.1:5180,http://localhost:5180')
  .split(',').map(value => value.trim()).filter(Boolean);
const server = createChatService({ allowedOrigins: origins });
server.on('error', error => {
  console.error('AI 對話服務無法啟動：', error.message); process.exitCode = 1;
});
server.listen(port, '127.0.0.1', () => console.log(`AI 對話 API：http://127.0.0.1:${port}`));
for (const signal of ['SIGINT', 'SIGTERM'] as const) {
  process.on(signal, () => { server.close(); server.closeAllConnections(); });
}
