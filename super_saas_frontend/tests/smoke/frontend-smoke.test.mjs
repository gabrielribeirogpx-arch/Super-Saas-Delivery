import test from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { setTimeout as delay } from 'node:timers/promises';
import fixtures from './fixtures/admin-smoke-fixtures.json' with { type: 'json' };
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const PORT = 3100;
const BASE_URL = `http://127.0.0.1:${PORT}`;

let server;

async function waitForServer(url, timeoutMs = 60000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
      // servidor ainda subindo
    }
    await delay(500);
  }
  throw new Error('Next.js não iniciou dentro do tempo esperado.');
}

test.before(async () => {
  server = spawn('npm', ['run', 'dev', '--', '--hostname', '127.0.0.1', '--port', String(PORT)], {
    cwd: path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..'),
    stdio: ['ignore', 'pipe', 'pipe'],
    env: { ...process.env, NEXT_TELEMETRY_DISABLED: '1' },
  });

  await waitForServer(`${BASE_URL}/login`);
});

test.after(async () => {
  if (server && !server.killed) {
    server.kill('SIGTERM');
    await delay(500);
  }
});

test('smoke login page renderiza formulário administrativo', async () => {
  const response = await fetch(`${BASE_URL}/login`);
  const html = await response.text();

  assert.equal(response.status, 200);
  assert.match(html, /Acesso administrativo/i);
  assert.match(html, /Tenant/i);
  assert.match(html, /admin@empresa\.com/i);
});

test('smoke páginas admin críticas respondem 200', async () => {
  const criticalPages = ['dashboard', 'orders', 'finance', 'users'];

  for (const page of criticalPages) {
    const response = await fetch(`${BASE_URL}/t/${fixtures.happyPath.login.tenantId}/${page}`);
    assert.equal(response.status, 200, `status inválido para ${page}`);
  }
});
