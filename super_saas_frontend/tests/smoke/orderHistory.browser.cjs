// Local fixtures only: no live API, customer data, messages or payments.
const puppeteer = require('puppeteer-core');
const assert = require('node:assert/strict');
const base = process.env.ORDER_HISTORY_TEST_BASE_URL || 'http://127.0.0.1:3044';
(async () => {
  const browser = await puppeteer.launch({ executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium', headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  try {
    for (const width of [320, 390, 1366]) {
      const page = await browser.newPage();
      await page.setViewport({ width, height: 900 });
      await page.setBypassServiceWorker(true);
      await page.evaluateOnNewDocument(() => { delete Navigator.prototype.serviceWorker; });
      const reads = [], errors = [];
      let legacyReads = 0, overviewReads = 0;
      page.on('pageerror', error => errors.push(error.message));
      await page.setRequestInterception(true);
      page.on('request', async request => {
        const url = new URL(request.url());
        const send = (status, data) => request.respond({ status, contentType: 'application/json', body: JSON.stringify(data) });
        if (url.pathname === '/api/admin/auth/me') return send(200, { id: 1, tenant_id: 1, name: 'Owner', role: 'owner', active: true });
        if (url.pathname === '/api/admin/billing/access') return send(200, { managed: false, active: true, features: {} });
        if (url.pathname === '/api/orders/1') { legacyReads++; return send(500, {}); }
        if (url.pathname === '/api/orders/1/overview') {
          overviewReads++;
          return send(200, { total: 24, summary: { today: 24, pending: 10, preparing: 5, delivering: 4, completed: 5 }, payments: ['PIX', 'DINHEIRO'], deliveries: ['ENTREGA', 'RETIRADA'] });
        }
        if (url.pathname === '/api/orders/1/search') {
          reads.push(Object.fromEntries(url.searchParams));
          await new Promise(resolve => setTimeout(resolve, 300));
          const filtered = Boolean(url.searchParams.get('customer'));
          const number = Number(url.searchParams.get('page'));
          const items = Array.from({ length: filtered ? 1 : 8 }, (_, i) => {
            const id = filtered ? 1 : 25 - (number - 1) * 8 - i;
            return { id, tenant_id: 1, daily_order_number: id, cliente_nome: filtered ? 'Cliente antigo' : `Cliente ${id}`, cliente_telefone: '11999999999', itens: 'Item sintético', endereco: '', tipo_entrega: 'RETIRADA', forma_pagamento: 'PIX', status: 'RECEBIDO', total_cents: 1500, valor_total: 1500, created_at: '2026-10-23T12:00:00Z' };
          });
          return send(200, { items, total: filtered ? 1 : 24, page: number, page_size: 8 });
        }
        if (url.pathname.startsWith('/api/')) return send(200, []);
        if (!['localhost', '127.0.0.1'].includes(url.hostname)) return request.abort();
        return request.continue();
      });
      await page.goto(base + '/orders', { waitUntil: 'domcontentloaded', timeout: 60000 });
      await page.waitForFunction(() => document.body.innerText.includes('1–8') && document.body.innerText.includes('de 24 pedidos'));
      await page.click('button[aria-label="Próxima página"]');
      await page.waitForFunction(() => document.body.innerText.includes('9–16'));
      assert.equal(overviewReads, 1);
      if (width < 1024) await page.click('.admin-orders-filters > summary');
      const input = 'input[placeholder="Buscar cliente"]';
      await page.type(input, 'Cliente antigo', { delay: 20 });
      await page.waitForFunction(() => document.body.innerText.includes('de 1 pedidos'));
      assert.equal(await page.$eval(input, el => el === document.activeElement), true);
      assert(reads.some(read => read.page === '2' && read.page_size === '8'));
      assert(reads.some(read => read.page === '1' && read.customer === 'Cliente antigo'));
      assert.equal(legacyReads, 0);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
      assert.equal(overflow, false);
      assert.deepEqual(errors, []);
      console.log('PASS paginated order history at ' + width + 'px');
      await page.close();
    }
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
