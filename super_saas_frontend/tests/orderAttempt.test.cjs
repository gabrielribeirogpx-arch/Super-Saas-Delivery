const { test, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const ts = require('typescript');
const path = require('node:path');
const base = path.join(__dirname, '../lib');
const originalWindow = Object.getOwnPropertyDescriptor(globalThis, 'window');
const originalFetch = globalThis.fetch;
if (!globalThis.crypto) Object.defineProperty(globalThis, 'crypto', { value: require('node:crypto').webcrypto });

function load() {
  for (const name of ['orderAttempt.ts', 'publicCheckout.ts']) delete require.cache[path.join(base, name)];
  const old = require.extensions['.ts'];
  require.extensions['.ts'] = (m, file) => m._compile(ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText, file);
  try { return { ...require('../lib/publicCheckout.ts'), ...require('../lib/orderAttempt.ts') }; }
  finally { require.extensions['.ts'] = old; }
}
function browser() {
  const data = new Map();
  Object.defineProperty(globalThis, 'window', { configurable: true, value: { localStorage: {
    getItem: key => data.get(key) ?? null, setItem: (key, value) => data.set(key, value), removeItem: key => data.delete(key),
  } } });
  return data;
}
const body = { customer_name: 'Pessoa privada', customer_phone: '11987654321', delivery_type: 'RETIRADA', items: [{ item_id: 1, quantity: 1 }] };
const ok = () => new Response(JSON.stringify({ order_number: 1, tracking_token: 'opaque-token', status: 'pending' }), { status: 200 });
afterEach(() => {
  globalThis.fetch = originalFetch;
  if (originalWindow) Object.defineProperty(globalThis, 'window', originalWindow); else Reflect.deleteProperty(globalThis, 'window');
});

test('a lost response and browser reload retain the key; UI completion retires it', async () => {
  const data = browser(), keys = [];
  globalThis.fetch = async (_, init) => {
    keys.push(new Headers(init.headers).get('Idempotency-Key'));
    if (keys.length === 1) throw new Error('Response lost after server commit');
    return ok();
  };
  const first = load();
  await assert.rejects(first.submitPublicOrder(body, 'alpha'));
  const reloaded = load();
  const response = await reloaded.submitPublicOrder(body, 'alpha');
  assert.equal(keys[0], keys[1]);
  assert.equal(data.size, 1);
  assert(![...data.values()].join().includes(body.customer_phone));
  assert(![...data.values()].join().includes(body.customer_name));
  reloaded.completeOrderAttempt(response);
  assert.equal(data.size, 0);
  await reloaded.submitPublicOrder(body, 'alpha');
  assert.notEqual(keys[2], keys[1]);
});

test('concurrent calls share a key; pending edits require an explicit new intent', async () => {
  browser(); const lib = load();
  const [a, b] = await Promise.all([lib.orderAttempt('alpha', body), lib.orderAttempt('alpha', { ...body })]);
  assert.equal(a.key, b.key);
  assert.notEqual((await lib.orderAttempt('beta', body)).key, a.key);
  await assert.rejects(lib.orderAttempt('alpha', { ...body, notes: 'Outra intenção' }), /pedido sem confirmação/);
  lib.startNewOrderAttempt('alpha');
  assert.notEqual((await lib.orderAttempt('alpha', { ...body, notes: 'Outra intenção' })).key, a.key);
});

test('blocked persistent storage still protects retries in the current page', async () => {
  Object.defineProperty(globalThis, 'window', { configurable: true, value: { get localStorage() { throw new Error('blocked'); } } });
  const lib = load();
  assert.equal((await lib.orderAttempt('alpha', body)).key, (await lib.orderAttempt('alpha', body)).key);
});

test('conflict and malformed success keep the attempt and never expose success', async () => {
  const data = browser(), lib = load();
  globalThis.fetch = async () => new Response('{}', { status: 409 });
  await assert.rejects(lib.submitPublicOrder(body, 'alpha'), /Confira seus pedidos/);
  const before = [...data.values()][0];
  globalThis.fetch = async () => new Response('{}', { status: 200 });
  await assert.rejects(lib.submitPublicOrder(body, 'alpha'), /mesma tentativa/);
  assert.equal([...data.values()][0], before);
});

test('acknowledging an earlier response cannot erase a newer attempt', async () => {
  const data = browser(), lib = load();
  globalThis.fetch = async () => ok();
  const old = await lib.submitPublicOrder(body, 'alpha');
  lib.startNewOrderAttempt('alpha');
  const next = await lib.orderAttempt('alpha', { ...body, notes: 'novo pedido' });
  lib.completeOrderAttempt(old);
  assert.equal(JSON.parse([...data.values()][0]).key, next.key);
});

test('an expired ambiguous attempt never silently becomes a new order', async () => {
  const data = browser(), lib = load();
  await lib.orderAttempt('alpha', body);
  const key = [...data.keys()][0], entry = JSON.parse(data.get(key));
  data.set(key, JSON.stringify({ ...entry, createdAt: Date.now() - 8 * 86400000 }));
  await assert.rejects(lib.orderAttempt('alpha', body), /tentativa é antiga/);
});

test('first validation failure can be corrected, but an uncertain retry cannot erase its key', async () => {
  const data = browser(), lib = load();
  globalThis.fetch = async () => new Response('{}', { status: 422 });
  await assert.rejects(lib.submitPublicOrder(body, 'alpha'));
  assert.equal(data.size, 0);
  globalThis.fetch = async () => { throw new Error('lost'); };
  await assert.rejects(lib.submitPublicOrder(body, 'alpha'));
  const saved = [...data.values()][0];
  globalThis.fetch = async () => new Response('{}', { status: 422 });
  await assert.rejects(lib.submitPublicOrder(body, 'alpha'));
  assert.equal([...data.values()][0], saved);
});
