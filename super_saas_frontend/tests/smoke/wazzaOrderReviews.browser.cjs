const assert = require('node:assert/strict');
const puppeteer = require('puppeteer-core');

const base = process.env.WAZZA_REVIEWS_TEST_BASE_URL || 'http://127.0.0.1:3044';

async function verifyQueue(browser, width) {
  const page = await browser.newPage();
  await page.setViewport({ width, height: 900 });
  await page.setBypassServiceWorker(true);
  await page.evaluateOnNewDocument(() => { delete Navigator.prototype.serviceWorker; });
  await page.setRequestInterception(true);
  const decisions = [];
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  let state = 'pending_review';
  page.on('request', request => {
    const url = new URL(request.url());
    const send = data => request.respond({ status: 200, contentType: 'application/json', body: JSON.stringify(data) });
    if (url.pathname === '/api/admin/auth/me') return send({ id: 1, tenant_id: 1, name: 'Operator', role: 'owner', active: true });
    if (url.pathname === '/api/admin/billing/access') return send({ managed: false, active: true, features: {} });
    if (url.pathname === '/api/orders/1/overview') return send({ total: 0, summary: {}, payments: [], deliveries: [] });
    if (url.pathname === '/api/orders/1/search') return send({ items: [], total: 0, page: 1, page_size: 8 });
    if (url.pathname === '/api/orders/wazza/requests/20/decision') {
      const data = JSON.parse(request.postData());
      decisions.push(data);
      state = data.action === 'approve' ? 'manual_resolution' : 'failed';
      return send({ state });
    }
    if (url.pathname === '/api/orders/wazza/requests') return send({
      next: null,
      items: [{
        request_id: 20, order_id: 40, action: 'edit', state, reason: 'benefits_or_stock',
        before_cents: 4500, after_cents: 3000, created_at: '2026-11-23T12:00:00Z',
        before_items: [{ name: 'Sanduíche com nome longo para verificar alinhamento', quantity: 3 }],
        after_items: [{ name: 'Sanduíche', quantity: 2, modifiers: [{ option_name: 'Queijo' }] }],
      }],
    });
    if (url.pathname.startsWith('/api/')) return send([]);
    if (!['localhost', '127.0.0.1'].includes(url.hostname)) return request.abort();
    return request.continue();
  });

  try {
    await page.goto(base + '/orders', { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.locator('::-p-text(Ver solicitações do WhatsApp)').click();
    await page.waitForFunction(() => document.body.innerText.includes('Pendente de análise'));
    assert.equal(await page.evaluate(() => document.body.innerText.includes('Queijo')), true);
    await page.type('#wazza-note-20', 'Autorizado pela loja');
    await page.$eval('article button:first-child', button => button.scrollIntoView({ block: 'center' }));
    await page.click('article button:first-child');
    await page.waitForFunction(() => document.body.innerText.includes('A solicitação foi aprovada, mas ainda não foi aplicada ao pedido'));
    await page.type('#wazza-note-20', 'Conferido nos registros');
    await page.$eval('article button:first-child', button => button.scrollIntoView({ block: 'center' }));
    await page.click('article button:first-child');
    await page.waitForFunction(() => document.body.innerText.includes('Falha na aplicação'));
    assert.deepEqual(decisions.map(entry => entry.action), ['approve', 'verify']);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false);
    assert.deepEqual(errors, []);
    console.log('PASS Wazza order review at ' + width + 'px');
  } catch (error) {
    console.error({ decisions, errors, text: await page.$eval('body', body => body.innerText.slice(-1500)) });
    throw error;
  } finally {
    await page.close();
  }
}

(async () => {
  const browser = await puppeteer.launch({
    executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium',
    headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  try {
    for (const width of [320, 390, 1366]) await verifyQueue(browser, width);
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
