// Visual and end-to-end checkout regression. All API responses and CEP lookup are fixtures.
const puppeteer = require('puppeteer-core');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const base = process.env.PREMIUM_CHECKOUT_TEST_BASE_URL || 'http://127.0.0.1:3053';
const artifacts = process.env.PREMIUM_CHECKOUT_ARTIFACT_DIR;
if (artifacts) fs.mkdirSync(artifacts, { recursive: true });
(async () => {
  const browser = await puppeteer.launch({ executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium', headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  try {
    for (const theme of ['white', 'dark']) for (const width of [320, 390, 768, 1366]) {
      const page = await browser.newPage();
      const errors = []; let posts = 0, payload;
      page.on('pageerror', error => errors.push(error.message));
      await page.setViewport({ width, height: 844 });
      await page.setBypassServiceWorker(true);
      await page.evaluateOnNewDocument(theme => {
        delete Navigator.prototype.serviceWorker; sessionStorage.clear(); localStorage.clear();
        localStorage.setItem('menu-theme', theme);
        localStorage.setItem('mobile-storefront-cart:alpha', JSON.stringify([{ id: 'cart-1', menuItemId: 1, name: 'Hambúrguer artesanal da casa com nome longo', price: 29.9, quantity: 1, totalPrice: 29.9, modifiers: [], note: 'Sem cebola' }]));
      }, theme);
      await page.setRequestInterception(true);
      page.on('request', request => {
        const url = new URL(request.url());
        const send = (status, data) => request.respond({ status, headers: { 'access-control-allow-origin': '*' }, contentType: 'application/json', body: JSON.stringify(data) });
        if (url.hostname === 'viacep.com.br') return send(200, { logradouro: 'Rua das Flores', bairro: 'Centro', localidade: 'São Paulo', uf: 'SP' });
        if (url.pathname === '/manifest.webmanifest') return send(200, {});
        if (url.pathname === '/api/public/menu') return send(200, { slug: 'alpha', tenant_id: 1, tenant: { name: 'Cozinha da Casa', is_open: true, delivery_fee: 5, estimated_prep_time: '25–40 min' }, public_settings: { theme: 'white', primary_color: '#dc2626' }, categories: [{ id: 1, name: 'Feitos na casa', items: [{ id: 1, name: 'Hambúrguer artesanal da casa', description: 'Pão artesanal, carne grelhada, queijo e molho da casa.', price_cents: 2990, featured: true }, { id: 2, name: 'Porção para compartilhar', description: 'Uma porção generosa para acompanhar seu pedido.', price_cents: 1890 }] }], items_without_category: [] });
        if (url.pathname === '/api/public/checkout-policy') return send(200, { methods: [{ id: 'pix', label: 'Pix direto da loja', available: true }, { id: 'card', label: 'Cartão na entrega', available: true }, { id: 'money', label: 'Dinheiro', available: true }, { id: 'native_pix', label: 'Pix online', available: false }], message: null });
        if (url.pathname === '/api/public/orders' && request.method() === 'POST') { posts++; payload = JSON.parse(request.postData()); return send(200, { order_number: 7, tracking_token: 'fixture-premium', total_cents: 3490, payment_method: payload.payment_method, order_type: payload.delivery_type, status: 'pending' }); }
        if (url.pathname === '/api/public/order/fixture-premium') return send(200, { order_number: 7, total_cents: 3490, payment_method: 'card', order_type: 'ENTREGA', status: 'pending' });
        if (url.pathname.startsWith('/api/')) return send(200, {});
        if (!['localhost', '127.0.0.1'].includes(url.hostname)) return request.abort();
        return request.continue();
      });
      const click = async text => {
        await page.waitForFunction(text => [...document.querySelectorAll('button')].some(b => b.textContent.trim() === text && !b.disabled), {}, text);
        await page.evaluate(text => [...document.querySelectorAll('button')].find(b => b.textContent.trim() === text).click(), text);
      };
      const fits = async stage => {
        await page.$eval('[role="dialog"]', e => Promise.all(e.getAnimations().map(a => a.finished)));
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), stage + ': page overflow');
        assert(await page.$eval('[role="dialog"]', e => e.scrollWidth <= e.clientWidth), stage + ': dialog overflow');
        assert(await page.$eval('[role="dialog"]', e => e.getBoundingClientRect().bottom <= innerHeight + 1), stage + ': modal exceeds viewport');
        assert(await page.$eval('[role="dialog"] footer button', e => { const r = e.getBoundingClientRect(); return r.height >= 44 && r.bottom <= innerHeight; }), stage + ': CTA inaccessible');
        const selected = await page.$eval('ol[aria-label="Etapas do pedido"] [aria-current="step"]', e => e.textContent);
        assert(selected, stage + ': missing active step');
        if (artifacts && width === 390) await page.screenshot({ path: path.join(artifacts, `${theme}-${stage}.png`) });
      };
      await page.goto(base + '/loja/alpha?preview=1', { waitUntil: 'domcontentloaded' });
      await page.waitForSelector('main[data-cart-bar-visible="true"]');
      await page.waitForFunction(theme => document.querySelector('main[data-theme]')?.dataset.theme === theme, {}, theme);
      if (artifacts && [390,1366].includes(width)) await page.screenshot({ path: path.join(artifacts, `${theme}-menu-${width}.png`), fullPage: true });
      await page.evaluate(() => window.dispatchEvent(new CustomEvent('storefront-open-cart')));
      await page.waitForSelector('[role="dialog"]');
      assert.equal(await page.$eval('[role="dialog"]', e => e.parentElement.dataset.theme), theme);
      await page.waitForFunction(() => document.body.style.overflow === 'hidden');
      await fits('cart');
      // Quantity editing updates totals and remains reversible.
      await page.click('button[aria-label^="Aumentar quantidade"]');
      assert.match(await page.$eval('[role="dialog"] footer', e => e.textContent), /64,80/);
      await page.click('button[aria-label^="Diminuir quantidade"]');
      await click('RETIRADA'); assert.match(await page.$eval('[role="dialog"] footer', e => e.textContent), /29,90/);
      assert.equal(await page.$$('ol[aria-label="Etapas do pedido"] li').then(x => x.length), 3);
      await click('ENTREGA'); assert.equal(await page.$$('ol[aria-label="Etapas do pedido"] li').then(x => x.length), 4);
      await click('Continuar'); await page.waitForSelector('input[placeholder="(11) 99999-9999"]'); await fits('identify');
      await page.type('input[placeholder="(11) 99999-9999"]', '11912345678'); await click('Continuar');
      await page.waitForSelector('input[placeholder="Seu nome"]'); await fits('customer');
      assert.match(await page.$eval('ol [aria-current="step"]', e => e.textContent), /Dados/);
      await page.type('input[placeholder="Seu nome"]', 'Cliente de teste'); await click('Continuar');
      await page.waitForSelector('input[placeholder="CEP *"]'); await fits('address');
      // Required address validation must remain in place.
      await click('Continuar'); await page.waitForFunction(() => document.body.textContent.includes('Campo obrigatório'));
      await page.type('input[placeholder="CEP *"]', '01001000'); await page.focus('input[placeholder="Número *"]');
      await page.waitForFunction(() => document.querySelector('input[placeholder="Cidade *"]').value === 'São Paulo');
      await page.type('input[placeholder="Número *"]', '42'); await click('Continuar');
      await page.waitForSelector('input[value="card"]'); await fits('payment');
      assert.equal(await page.$eval('input[value="native_pix"]', e => e.disabled), true);
      await page.click('input[value="card"]');
      await page.click('details summary'); await page.type('input[placeholder="Cupom"]', 'casa');
      await page.type('textarea', 'Interfone 42');
      // Focus stays in the modal, including its optional fields and footer.
      await page.focus('[aria-label="Voltar"]'); await page.keyboard.down('Shift'); await page.keyboard.press('Tab'); await page.keyboard.up('Shift');
      assert.equal(await page.evaluate(() => document.activeElement.textContent.trim()), 'Confirmar pedido');
      await page.keyboard.press('Tab'); assert.equal(await page.evaluate(() => document.activeElement.getAttribute('aria-label')), 'Voltar');
      // Short viewport emulates the reduced space left by an onscreen keyboard.
      await page.setViewport({ width, height: 540 }); await fits('keyboard'); await page.setViewport({ width, height: 844 });
      await click('Confirmar pedido'); await page.waitForFunction(() => document.body.textContent.includes('Pedido #7 recebido!'));
      assert.equal(posts, 1); assert.equal(payload.delivery_type, 'ENTREGA'); assert.equal(payload.delivery_address.number, '42'); assert.equal(payload.payment_method, 'card'); assert.equal(payload.coupon_code, 'CASA'); assert.equal(payload.notes, 'Interfone 42');
      await click('Voltar ao cardápio'); await page.waitForFunction(() => !document.querySelector('[role="dialog"]')); assert.equal(await page.evaluate(() => document.body.style.overflow), '');
      assert.deepEqual(errors, []);
      console.log(`PASS premium checkout ${theme} ${width}px: delivery, validation, totals, focus, short viewport, single submission`);
      await page.close();
    }
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
