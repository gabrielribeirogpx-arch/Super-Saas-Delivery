// Full checkout against local fixtures; no live backend or payment provider.
const puppeteer = require('puppeteer-core');
const assert = require('node:assert/strict');
const base = process.env.ORDER_ATTEMPT_TEST_BASE_URL || 'http://127.0.0.1:3045';
(async () => {
  const browser = await puppeteer.launch({ executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium', headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  try {
    for (const width of [390, 1366]) {
      const page = await browser.newPage();
      const context = page.browserContext();
      const keys = [], orders = new Map(), errors = [];
      let posts = 0;
      await page.setViewport({ width, height: 900 });
      await page.setBypassServiceWorker(true);
      page.on('pageerror', error => errors.push(error.message));
      await page.evaluateOnNewDocument(() => {
        delete Navigator.prototype.serviceWorker;
        sessionStorage.clear(); localStorage.clear();
        localStorage.setItem('mobile-storefront-cart:alpha', JSON.stringify([{ id: 'cart-1', menuItemId: 1, name: 'Burger', price: 25, quantity: 1, totalPrice: 25, modifiers: [], note: '' }]));
      });
      await page.setRequestInterception(true);
      page.on('request', request => {
        const url = new URL(request.url());
        const send = (status, data) => request.respond({ status, contentType: 'application/json', body: JSON.stringify(data) });
        if (url.pathname === '/manifest.webmanifest') return send(200, {});
        if (url.pathname === '/api/public/menu') return send(200, { slug: 'alpha', tenant_id: 1, tenant: { name: 'Alpha', is_open: true, delivery_fee: 0 }, public_settings: { theme: 'white', primary_color: '#dc2626' }, categories: [{ id: 1, name: 'Burgers', items: [{ id: 1, name: 'Burger', price_cents: 2500 }] }], items_without_category: [] });
        if (url.pathname === '/api/public/checkout-policy') return send(200, { methods: [{ id: 'card', label: 'Cartão com a loja', available: true }], message: null });
        if (url.pathname === '/api/public/orders' && request.method() === 'POST') {
          posts++;
          const key = request.headers()['idempotency-key'];
          keys.push(key);
          assert(key && key.length >= 32);
          if (!orders.has(key)) orders.set(key, { order_number: 1, daily_order_number: 1, tracking_token: 'fixture-order-token', total_cents: 2500, status: 'pending', payment_method: 'card', order_type: 'pickup' });
          if (posts === 1) return request.abort('failed'); // Server committed; reply was lost.
          return send(200, orders.get(key));
        }
        if (url.pathname === '/api/public/order/fixture-order-token') return send(200, { order_number: 1, status: 'pending', total_cents: 2500, payment_method: 'card', order_type: 'pickup' });
        if (url.pathname.startsWith('/api/')) return send(200, {});
        if (!['127.0.0.1', 'localhost'].includes(url.hostname)) return request.abort();
        return request.continue();
      });
      await page.goto(base + '/loja/alpha?preview=1', { waitUntil: 'domcontentloaded', timeout: 120000 });
      await page.waitForFunction(() => [...document.querySelectorAll('button')].some(b => b.textContent.includes('Ver carrinho')) || document.querySelector('main[data-cart-bar-visible="true"]'));
      await page.evaluate(() => window.dispatchEvent(new CustomEvent('storefront-open-cart')));
      await page.waitForFunction(() => document.body.textContent.includes('Tipo de pedido'));
      assert.equal(await page.$$eval('[aria-label="Pagamento"]', elements => elements.length), 0);
      const click = async text => {
        await page.waitForFunction(value => [...document.querySelectorAll('button')].some(b => b.textContent.trim() === value && !b.disabled), {}, text);
        return page.evaluate(value => [...document.querySelectorAll('button')].find(b => b.textContent.trim() === value).click(), text);
      };
      await click('RETIRADA'); await click('Continuar');
      await page.waitForSelector('input[placeholder="(11) 99999-9999"]');
      await page.type('input[placeholder="(11) 99999-9999"]', '11912345678'); await click('Continuar');
      await page.waitForSelector('input[placeholder="Seu nome"]');
      await page.type('input[placeholder="Seu nome"]', 'Cliente sintético'); await click('Continuar');
      await page.waitForSelector('input[value="card"]'); await page.click('input[value="card"]');
      await click('Confirmar pedido');
      await page.waitForFunction(() => document.body.textContent.includes('mesma tentativa'));
      assert(await page.evaluate(() => localStorage.getItem('mobile-storefront-cart:alpha')));
      assert.equal(await page.evaluate(() => Object.keys(localStorage).filter(k => k.startsWith('fomizero:order-attempt:')).length), 1);
      const nameInput = 'input[placeholder="Seu nome"]';
      const originalName = await page.$eval(nameInput, input => input.value);
      await page.type(nameInput, ' Alterado');
      await click('Confirmar pedido');
      await page.waitForFunction(() => document.body.textContent.includes('pedido sem confirmação com outros dados'));
      assert.equal(posts, 1); // Editing an uncertain request must not silently create another order.
      assert(await page.evaluate(() => [...document.querySelectorAll('button')].some(b => b.textContent.includes('Já conferi: iniciar outro pedido'))));
      await page.focus(nameInput); await page.$eval(nameInput, input => input.select());
      await page.keyboard.press('Backspace'); await page.type(nameInput, originalName);
      assert.equal(await page.$eval(nameInput, input => input.value), originalName);
      await click('Confirmar pedido');
      await page.waitForFunction(() => document.body.textContent.includes('Pedido #1 recebido!'));
      assert.equal(posts, 2); assert.equal(orders.size, 1); assert.equal(keys[0], keys[1]);
      assert.equal(await page.evaluate(() => Object.keys(localStorage).filter(k => k.startsWith('fomizero:order-attempt:')).length), 0);
      assert.deepEqual(errors, []);
      console.log('PASS lost reply and same-attempt checkout retry at ' + width + 'px');
      await page.close();
    }
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
