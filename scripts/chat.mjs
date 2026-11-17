import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';
import { createServer } from 'node:net';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const [major, minor] = process.versions.node.split('.').map(Number);
if (major < 24 || (major === 24 && minor < 12)) {
  console.error('請先安裝 Node.js 24.12 以上版本，再執行這份程式。');
  process.exit(1);
}
const env = { ...process.env, PATH: dirname(process.execPath) + (process.platform === 'win32' ? ';' : ':') + process.env.PATH };
const command = process.argv[2] || 'dev';
const config = JSON.parse(readFileSync(join(root, 'chat.config.json'), 'utf8'));
for (const key of ['frontendPort', 'apiPort']) {
  if (!Number.isInteger(config[key]) || config[key] < 1024 || config[key] > 65535) throw new Error('chat.config.json 的連接埠須介於 1024–65535。');
}
if (config.frontendPort === config.apiPort) throw new Error('前端和 AI API 必須使用不同連接埠。');
const frontend = join(root, 'frontend');
const ai = join(root, 'ai');
function runNode(args, cwd = root) {
  return new Promise((resolveRun, reject) => {
    const child = spawn(process.execPath, args, { cwd, env, stdio: 'inherit', windowsHide: true });
    child.on('error', reject);
    child.on('exit', code => code === 0 ? resolveRun() : reject(new Error('指令未完成，請查看上方錯誤。')));
  });
}
async function install() {
  // Reuse the frontend's original pnpm lockfile.
  const npm = process.env.npm_execpath;
  if (!npm || !existsSync(npm)) throw new Error('請從本資料夾用 npm run setup 啟動安裝。');
  await runNode([npm, 'exec', '--yes', '--package=pnpm@12.6.0', '--', 'pnpm', 'install', '--frozen-lockfile'], frontend);
  await runNode([npm, 'ci', '--no-audit', '--no-fund'], ai);
}
async function ensureWorker() {
  if (!existsSync(join(frontend, 'public/mockServiceWorker.js'))) {
    await runNode(['node_modules/msw/cli/index.js', 'init', 'public', '--no-save'], frontend);
  }
}
function configure() {
  if (!existsSync(join(ai, '.env.local'))) {
    writeFileSync(join(ai, '.env.local'), readFileSync(join(ai, '.env.example')));
  }
  console.log('設定完成。請填寫 ai/.env.local 的 OPENROUTER_API_KEY，再執行 npm run dev。');
}
async function assertFree(port) {
  await new Promise((resolveFree, reject) => {
    const check = createServer();
    check.once('error', () => reject(new Error('連接埠 ' + port + ' 已被使用。請關閉先前的程式，或修改 chat.config.json。')));
    check.listen(port, '127.0.0.1', () => check.close(resolveFree));
  });
}
async function dev(mockOnly) {
  for (const path of [join(frontend, 'node_modules/vite/bin/vite.js'), join(ai, 'node_modules/zod')]) {
    if (!existsSync(path)) throw new Error('尚未安裝套件，請先在本資料夾執行 npm run setup。');
  }
  await ensureWorker();
  await assertFree(config.frontendPort);
  if (!mockOnly) await assertFree(config.apiPort);
  const children = [];
  let stopping = false;
  const stop = () => {
    if (stopping) return;
    stopping = true;
    for (const child of children) child.kill();
  };
  process.on('SIGINT', stop);
  process.on('SIGTERM', stop);
  const launch = (args, cwd, extraEnv) => {
    const child = spawn(process.execPath, args, {
      cwd, env: { ...env, ...extraEnv }, stdio: 'inherit', windowsHide: true,
    });
    children.push(child);
    child.once('error', error => { console.error(error.message); process.exitCode = 1; stop(); });
    child.once('exit', code => { if (!stopping) { process.exitCode = code || 1; stop(); } });
  };
  if (!mockOnly) launch(['--env-file-if-exists=.env.local', 'server.ts'], ai, {
    CHAT_API_PORT: String(config.apiPort),
    CHAT_ALLOWED_ORIGINS: 'http://127.0.0.1:' + config.frontendPort + ',http://localhost:' + config.frontendPort,
  });
  launch([join(frontend, 'node_modules/vite/bin/vite.js'), '--mode', 'mock', '--host', '127.0.0.1', '--port', String(config.frontendPort), '--strictPort'], frontend, {
    VITE_USE_MOCK: 'true', VITE_CHAT_API_ENABLED: mockOnly ? 'false' : 'true',
    VITE_CHAT_API_URL: 'http://127.0.0.1:' + config.apiPort,
  });
  console.log('PR205 聊天頁：http://127.0.0.1:' + config.frontendPort + '/login');
  console.log(mockOnly ? '原始假對話模式。按 Ctrl+C 關閉。' : '登入 s012 / password123 → 哲學概論 → 善意的謊言是對的嗎？ 按 Ctrl+C 關閉。');
}
try {
  if (command === 'install') await install();
  else if (command === 'setup') {
    if (!process.argv.includes('--config-only')) await install();
    if (existsSync(join(frontend, 'node_modules/msw'))) await ensureWorker();
    configure();
  } else if (command === 'dev' || command === 'mock') await dev(command === 'mock');
  else if (command === 'check') {
    await ensureWorker();
    await runNode(['node_modules/typescript/bin/tsc', '--noEmit'], ai);
    await runNode(['--test', 'tests/*.test.mjs'], ai);
    await runNode(['node_modules/oxlint/bin/oxlint', '.'], frontend);
    await runNode(['node_modules/eslint/bin/eslint.js', '.'], frontend);
    await runNode(['node_modules/prettier/bin/prettier.cjs', '--check',
      'src/api/chat.ts', 'src/composables/useChatStream.ts', 'src/views/student/ChatView.vue'], frontend);
    await runNode(['node_modules/vue-tsc/bin/vue-tsc.js', '--build'], frontend);
    await runNode(['node_modules/vitest/vitest.mjs', 'run'], frontend);
    env.VITE_CHAT_API_ENABLED = 'true';
    env.VITE_CHAT_API_URL = 'http://127.0.0.1:' + config.apiPort;
    await runNode(['node_modules/vite/bin/vite.js', 'build', '--mode', 'mock'], frontend);
  } else throw new Error('未知指令：' + command);
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
