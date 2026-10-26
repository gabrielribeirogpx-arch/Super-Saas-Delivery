const { test, afterEach } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const ts = require('typescript');
const oldLoad = Module._load, oldTs = require.extensions['.ts'];
Module._load = function(request, parent, isMain) {
  if (request.startsWith('@/lib/')) request = path.join(__dirname, '..', request.slice(2)) + '.ts';
  return oldLoad.call(this, request, parent, isMain);
};
require.extensions['.ts'] = (module, filename) => module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true },
}).outputText, filename);
const auth = require('../lib/customerAuth.ts');
Module._load = oldLoad; require.extensions['.ts'] = oldTs;
const oldWindow = Object.getOwnPropertyDescriptor(globalThis, 'window'), oldFetch = globalThis.fetch;
afterEach(() => {
  if (oldWindow) Object.defineProperty(globalThis, 'window', oldWindow); else Reflect.deleteProperty(globalThis, 'window');
  globalThis.fetch = oldFetch;
});
function storage(values = {}) {
  const map = new Map(Object.entries(values));
  return { get length() { return map.size; }, key: index => [...map.keys()][index] ?? null,
    getItem: key => map.get(key) ?? null, setItem: (key,value) => map.set(key,value), removeItem: key => map.delete(key) };
}
function browser() {
  const sessionStorage = storage({ 'storefront:tracking-order:old': 'private', 'storefront:tracking-order:latest:burger': 'old', 'storefront:order-summary-open:burger': 'old', 'customer-auth-phone:burger': 'phone', 'unrelated': 'keep' });
  const localStorage = storage({ 'service-delivery:burger:customer-orders': '["old"]', 'mobile-storefront-cart:burger': 'new cart' });
  Object.defineProperty(globalThis, 'window', { configurable: true, value: { sessionStorage, localStorage, dispatchEvent: () => true,
    location: { hostname:'localhost', pathname:'/account', search:'?tenant=burger' } } });
  return {sessionStorage, localStorage};
}
test('logout clears order shortcuts and pending phone but keeps a new cart', async () => {
  const b = browser(); globalThis.fetch = async () => Response.json({ok:true});
  await auth.logoutCustomer();
  assert.equal(b.sessionStorage.getItem('storefront:tracking-order:old'),null);
  assert.equal(b.sessionStorage.getItem('storefront:order-summary-open:burger'),null);
  assert.equal(b.sessionStorage.getItem('customer-auth-phone:burger'),null);
  assert.equal(b.sessionStorage.getItem('unrelated'),'keep');
  assert.equal(b.localStorage.getItem('service-delivery:burger:customer-orders'),null);
  assert.equal(b.localStorage.getItem('mobile-storefront-cart:burger'),'new cart');
});
test('failed logout clears shortcuts but does not report cookie logout success', async () => {
  const b=browser(); globalThis.fetch = async () => { throw new Error('Network offline'); };
  await assert.rejects(auth.logoutCustomer(),/Network offline/);
  assert.equal(b.sessionStorage.getItem('storefront:tracking-order:old'),null);
});
test('failed OTP request does not pretend a message was delivered', async () => {
  browser(); globalThis.fetch = async () => Response.json({detail:'Acesso por código ainda indisponível'},{status:503});
  await assert.rejects(auth.requestCustomerCode('11912345678',true),/indisponível/);
});
test('verified account switch clears previous shortcuts and keeps tenant context', async () => {
  const b=browser(); let request;
  globalThis.fetch=async (url,init) => { request={url,init}; return Response.json({ok:true}); };
  await auth.verifyCustomerCode('11912345678','123456');
  assert.equal(b.sessionStorage.getItem('storefront:tracking-order:old'),null);
  assert.match(request.url,/tenant=burger/);
  assert.equal(request.init.credentials,'include');
  assert.equal(auth.customerAccountUrl('/account/orders'),'/account/orders?tenant=burger');
});
