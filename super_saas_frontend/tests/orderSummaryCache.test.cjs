const { test, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const ts = require('typescript');
const previousLoader = require.extensions['.ts'];
require.extensions['.ts'] = (module, filename) => module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText, filename);
const { cacheTrackingOrder, getLatestCachedTrackingOrder, getOpenOrderSummary, setOpenOrderSummary } = require('../lib/orderTrackingCache.ts');
require.extensions['.ts'] = previousLoader;
const originalWindow = Object.getOwnPropertyDescriptor(globalThis, 'window');
afterEach(() => {
  if (originalWindow) Object.defineProperty(globalThis, 'window', originalWindow);
  else Reflect.deleteProperty(globalThis, 'window');
});
function browser() {
  const data = new Map();
  Object.defineProperty(globalThis, 'window', { configurable: true, value: {
    sessionStorage: { getItem: key => data.get(key) ?? null, setItem: (key, value) => data.set(key, value), removeItem: key => data.delete(key) },
    dispatchEvent: () => true,
  } });
  return data;
}
const order = { token: 'opaque-order-token', tenant: 'burger', orderNumber: 4, totalCents: 2990, subtotalCents: 2490, deliveryFeeCents: 500, pointsEarned: 29 };
test('refresh restores selected summary and preserves order amounts', () => {
  browser(); cacheTrackingOrder(order); setOpenOrderSummary('burger', order.token);
  assert.equal(getOpenOrderSummary('burger').orderNumber, 4);
  assert.equal(getOpenOrderSummary('burger').totalCents, 2990);
  assert.equal(getOpenOrderSummary('burger').subtotalCents, 2490);
  assert.equal(getOpenOrderSummary('burger').pointsEarned, 29);
  setOpenOrderSummary('burger', null);
  assert.equal(getOpenOrderSummary('burger'), null);
  assert.equal(getLatestCachedTrackingOrder('burger').token, order.token);
});
test('orders survive thirty minutes but expire from session cache after twenty-four hours', () => {
  const data = browser(); cacheTrackingOrder(order);
  const key = 'storefront:tracking-order:' + order.token;
  const saved = JSON.parse(data.get(key));
  data.set(key, JSON.stringify({ ...saved, createdAt: Date.now() - 2 * 60 * 60 * 1000 }));
  assert.equal(getLatestCachedTrackingOrder('burger').token, order.token);
  data.set(key, JSON.stringify({ ...saved, createdAt: Date.now() - 25 * 60 * 60 * 1000 }));
  assert.equal(getLatestCachedTrackingOrder('burger'), null);
});
test('a tenant cannot restore another tenant cached summary', () => {
  const data = browser(); cacheTrackingOrder(order); setOpenOrderSummary('other', order.token);
  data.set('storefront:tracking-order:latest:other', order.token);
  assert.equal(getOpenOrderSummary('other'), null);
  assert.equal(getLatestCachedTrackingOrder('other'), null);
});
test('legacy cached orders do not invent an absent subtotal', () => {
  browser(); cacheTrackingOrder({ token: 'old-order', tenant: 'burger', totalCents: 2990 });
  assert.equal(getLatestCachedTrackingOrder('burger').totalCents, 2990);
  assert.equal(getLatestCachedTrackingOrder('burger').subtotalCents, undefined);
});
test('blocked storage does not break the menu', () => {
  Object.defineProperty(globalThis, 'window', { configurable: true, value: {
    get sessionStorage() { throw new Error('Storage blocked'); }, dispatchEvent: () => true,
  } });
  cacheTrackingOrder(order); setOpenOrderSummary('burger', order.token);
  assert.equal(getOpenOrderSummary('burger'), null);
});
