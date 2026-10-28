const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../lib/salesAnalytics.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;

function analytics(hostname, pathname, accepted = false) {
  const scripts = [];
  const location = { hostname, pathname, origin: `https://${hostname}`, hash: '', search: '?plan=operation&invite=private' };
  const window = { location };
  const document = {
    title: 'Fomizero',
    createElement: () => ({}),
    head: { appendChild: script => scripts.push(script) },
  };
  const module = { exports: {} };
  const requireStub = id => {
    if (id === '@/lib/metaPixel') return { advertisingConsent: () => accepted };
    if (id === '@/lib/platformDomains') return { extractPlatformTenantSlug: host => host.endsWith('.fomizero.com.br') && !host.startsWith('www.') ? 'restaurant' : null };
    throw new Error(`Unexpected import: ${id}`);
  };
  vm.runInNewContext(compiled, { module, exports: module.exports, require: requireStub, window, document, Date });
  return { api: module.exports, scripts, window, location, accept: () => { accepted = true; } };
}

test('GA4 is restricted to Fomizero sales pages and requires fresh consent', () => {
  const shop = analytics('meuburger.fomizero.com.br', '/loja/meuburger', true);
  shop.api.loadSalesAnalytics();
  assert.equal(shop.scripts.length, 0);
  assert.equal(shop.api.isSalesAnalyticsPage(shop.location.hostname, shop.location.pathname), false);

  const lead = analytics('www.fomizero.com.br', '/onboarding');
  lead.api.loadSalesAnalytics();
  assert.equal(lead.scripts.length, 0);
  lead.accept();
  lead.api.loadSalesAnalytics();
  assert.equal(lead.scripts.length, 1);
  assert.equal(lead.scripts[0].src, 'https://www.googletagmanager.com/gtag/js?id=G-HDBVG6L1NT');
  lead.scripts[0].onload();
  const views = lead.window.dataLayer.filter(call => call[0] === 'event' && call[1] === 'page_view');
  assert.equal(views.length, 1);
  assert.equal(views[0][2].page_location, 'https://www.fomizero.com.br/onboarding');
  assert.equal(views[0][2].page_path, '/onboarding');
  lead.api.trackSalesAnalyticsEvent('begin_checkout', { code: 'operation', price_cents: 17990 });
  assert.equal(lead.window.dataLayer.filter(call => call[1] === 'begin_checkout').length, 1);
  lead.location.pathname = '/loja/meuburger';
  lead.api.revokeSalesAnalytics();
  lead.api.trackSalesAnalyticsEvent('begin_checkout');
  assert.equal(lead.window.dataLayer.filter(call => call[1] === 'begin_checkout').length, 1);
  assert.equal(lead.window.dataLayer.at(-1)[2].analytics_storage, 'denied');
});

test('the owner subscription page is eligible, customer checkout is not', () => {
  const owner = analytics('meuburger.fomizero.com.br', '/subscriptions', true);
  assert.equal(owner.api.isSalesAnalyticsPage(owner.location.hostname, owner.location.pathname), true);
  const customer = analytics('meuburger.fomizero.com.br', '/checkout', true);
  assert.equal(customer.api.isSalesAnalyticsPage(customer.location.hostname, customer.location.pathname), false);
});
