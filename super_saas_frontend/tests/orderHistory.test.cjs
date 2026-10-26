const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const ts = require('typescript');
const Module = require('node:module');
const filename = require('node:path').join(__dirname, '../lib/orderHistory.ts');
const compiled = new Module(filename, module);
compiled._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText, filename);
const { orderHistoryQuery, orderOverviewQuery } = compiled.exports;

test('history sends filters and pagination to the server, escaping customer input', () => {
  const params = new URLSearchParams(orderHistoryQuery({ order: '123', customer: 'José & Filhos', status: 'EM_PREPARO', payment: 'PIX', delivery: 'RETIRADA', date: '2026-10-23' }, 3));
  assert.equal(params.get('page'), '3');
  assert.equal(params.get('page_size'), '8');
  assert.equal(params.get('customer'), 'José & Filhos');
  assert.equal(params.get('order_number'), '123');
  assert.equal(params.get('created_on'), '2026-10-23');
  assert.equal(params.get('status'), 'EM_PREPARO');
});

test('overview describes browser local day independently of filtered pages', () => {
  const now = new Date(2026, 9, 23, 23, 50);
  const params = new URLSearchParams(orderOverviewQuery(now));
  assert.equal(params.get('today'), '2026-10-23');
  assert.equal(params.get('utc_offset_minutes'), String(now.getTimezoneOffset()));
  assert.equal(params.has('page'), false);
});
