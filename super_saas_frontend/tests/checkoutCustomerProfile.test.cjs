const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const ts = require('typescript');
const previousLoader = require.extensions['.ts'];
require.extensions['.ts'] = (module, filename) => module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText, filename);
const { loadCheckoutCustomerProfile, saveCheckoutCustomerProfile } = require('../lib/checkoutCustomerProfile.ts');
require.extensions['.ts'] = previousLoader;

function memoryStorage() {
  const data = new Map();
  return {
    getItem: key => data.get(key) ?? null,
    setItem: (key, value) => data.set(key, value),
  };
}

test('dados e endereço persistem por restaurante para a próxima compra', () => {
  const storage = memoryStorage();
  const profile = { id: 0, name: 'Gabriel', phone: '11999999999', email: 'gabriel@example.com', addresses: [
    { id: 1, zip: '14813132', street: 'Rua Teste', number: '67', neighborhood: 'Centro', city: 'Gavião Peixoto', state: 'SP', is_default: true },
  ] };
  saveCheckoutCustomerProfile(storage, 'loja-a', profile);
  assert.deepEqual(loadCheckoutCustomerProfile(storage, 'loja-a'), profile);
  assert.equal(loadCheckoutCustomerProfile(storage, 'loja-b'), null);
});

test('cadastro inválido ou incompleto não preenche o checkout', () => {
  const storage = memoryStorage();
  storage.setItem('storefront-checkout-profile:loja-a', '{invalid');
  assert.equal(loadCheckoutCustomerProfile(storage, 'loja-a'), null);
  storage.setItem('storefront-checkout-profile:loja-a', JSON.stringify({ name: 'Teste', phone: '123' }));
  assert.equal(loadCheckoutCustomerProfile(storage, 'loja-a'), null);
});
