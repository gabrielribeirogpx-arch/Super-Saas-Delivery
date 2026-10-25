// End-to-end driver UX with synthetic session, GPS and API fixtures. No real delivery or messages.
const puppeteer = require('puppeteer-core');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const base = process.env.DRIVER_EXPERIENCE_TEST_BASE_URL || 'http://127.0.0.1:3055';
const artifacts = process.env.DRIVER_EXPERIENCE_ARTIFACT_DIR;
if (artifacts) fs.mkdirSync(artifacts, { recursive: true });
(async () => {
 const browser = await puppeteer.launch({ executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium', headless: true, args: ['--no-sandbox','--disable-dev-shm-usage'] });
 try {
  for (const width of [320,390,768,1366]) {
   const context = await browser.createBrowserContext(); await context.overridePermissions(base, ["geolocation"]); const page = await context.newPage();
   let phase = 'available', acceptCalls = 0, startCalls = 0, completeCalls = 0;
   const errors = [];
   page.on('pageerror', e => errors.push(e.message));
   await page.setViewport({ width, height: 844 }); await page.setBypassServiceWorker(true);
   await page.setCookie({ name: 'driver_session', value: '1', url: base, path: '/driver' });
   await page.evaluateOnNewDocument(() => {
    delete Navigator.prototype.serviceWorker;
    localStorage.setItem('driver_token', 'synthetic-driver-session');
    window.__driverOffline = false; window.__denyGPS = false;
    Object.defineProperty(navigator, 'onLine', { get: () => !window.__driverOffline, configurable: true });
    const sample = () => ({ coords: { latitude: -21.0, longitude: -48.0, accuracy: 10, heading: null, speed: 0 }, timestamp: Date.now() });
    Object.defineProperty(navigator, 'geolocation', { value: {
     getCurrentPosition: (ok, fail) => window.__denyGPS ? fail({ code: 1, message: 'Permission denied' }) : ok(sample()),
     watchPosition: ok => { ok(sample()); return 1; }, clearWatch: () => {},
    }, configurable: true });
   });
   await page.setRequestInterception(true);
   page.on('request', async request => {
    const url = new URL(request.url());
    const send = (status, data) => request.respond({ status, contentType: 'application/json', body: JSON.stringify(data) });
    const order = { id: 7, daily_order_number: 12, status: phase === 'available' ? 'READY_FOR_DELIVERY' : phase === 'assigned' ? 'DRIVER_ASSIGNED' : phase === 'moving' ? 'OUT_FOR_DELIVERY' : 'DELIVERED', customer_name: 'Cliente com nome completo e sobrenome', address: 'Rua das Flores, 42, Centro, São Paulo — SP', complement: 'Bloco B, apartamento 42', reference: 'Portaria principal', phone: '11912345678', payment_method: 'money', total_cents: 4590, change_for: 'R$ 50,00', items: '1x Hambúrguer da casa\n1x Suco', notes: 'Chamar pelo interfone', customer_lat: null, customer_lng: null };
    if (url.pathname === '/api/driver/state') return send(200, { driver: { id: 1, name: 'Marina Souza', email: 'fixture@example.com', restaurant_id: 1, role: 'driver' }, active_delivery: ['assigned','moving'].includes(phase) ? order : null, assigned_orders: ['assigned','moving'].includes(phase) ? [order] : [], available_orders: phase === 'available' ? [order] : [], completed_today: phase === 'delivered' ? 1 : 0 });
    if (url.pathname.endsWith('/7/accept')) { acceptCalls++; await new Promise(resolve => setTimeout(resolve,150)); if (acceptCalls === 1) return send(409, { detail: 'Pedido já atribuído' }); phase = 'assigned'; return send(200, { ok: true, status: 'DRIVER_ASSIGNED' }); }
    if (url.pathname.endsWith('/7/start')) { startCalls++; if (startCalls === 1) return send(500, { detail: 'Falha temporária' }); phase = 'moving'; return send(200, { ok: true, status: 'OUT_FOR_DELIVERY' }); }
    if (url.pathname.endsWith('/7/complete')) { completeCalls++; if (completeCalls === 1) return send(500, { detail: 'Falha temporária' }); phase = 'delivered'; return send(200, { ok: true, status: 'DELIVERED' }); }
    if (url.pathname.startsWith('/api/')) return send(200, {});
    if (!['127.0.0.1','localhost'].includes(url.hostname)) return request.abort();
    return request.continue();
   });
   const click = async text => {
    await page.waitForFunction(text => [...document.querySelectorAll('button')].some(b => b.textContent.trim() === text && !b.disabled), {}, text);
    await page.evaluate(text => [...document.querySelectorAll('button')].find(b => b.textContent.trim() === text).click(), text);
   };
   const fits = async name => {
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), name + ': overflow');
    const actions = await page.$('[aria-label="Detalhes da entrega"] > div:last-child button');
    if (actions) assert(await actions.evaluate(e => { const r = e.getBoundingClientRect(); const nav = document.querySelector('nav[aria-label="Navegação do entregador"]').getBoundingClientRect(); return r.height >= 44 && r.bottom <= nav.top; }), name + ': action hidden by navigation');
    if (artifacts && [390,1366].includes(width)) await page.screenshot({ path: path.join(artifacts, `${name}-${width}.png`), fullPage: name === 'dashboard' });
   };
   await page.goto(base + '/driver/dashboard', { waitUntil: 'domcontentloaded' });
   await page.waitForFunction(() => document.body.textContent.includes('Pedido #12')); await fits('dashboard');
   assert(!await page.evaluate(() => document.body.textContent.includes('Prioridade normal')));
   // Offline and failed acceptance must never advance to the active route.
   await page.evaluate(() => { window.__driverOffline = true; window.dispatchEvent(new Event('offline')); });
   await page.waitForFunction(() => [...document.querySelectorAll('button')].find(b => b.textContent.includes('Aceitar entrega'))?.disabled);
   assert.equal(acceptCalls, 0);
   await page.evaluate(() => { window.__driverOffline = false; window.dispatchEvent(new Event('online')); });
   await page.evaluate(() => { const button = [...document.querySelectorAll('button')].find(b => b.textContent.trim() === 'Aceitar entrega'); button.click(); button.click(); });
   await page.waitForFunction(() => document.body.textContent.includes('Não foi possível confirmar a entrega'));
   assert.equal(acceptCalls,1); assert.equal(new URL(page.url()).pathname,'/driver/dashboard');
   await click('Aceitar entrega');
   await page.waitForSelector('[aria-label="Detalhes da entrega"]');
   await page.waitForFunction(() => [...document.querySelectorAll('button')].some(b => b.textContent.trim() === 'Iniciar entrega'));
   assert.equal(acceptCalls,2); await fits('assigned');
   assert.equal(await page.$('button[onclick="handleComplete"]'), null);
   assert.equal(await page.$$eval('a', es => es.some(e => e.textContent.includes('Google Maps') && e.href.includes('destination=Rua'))), true);
   assert.equal(await page.$$eval('a', es => es.some(e => e.textContent.includes('WhatsApp') && e.href.startsWith('https://wa.me/'))), true);
   assert(!await page.evaluate(() => document.body.textContent.includes('Cheguei ao local') || document.body.textContent.includes('Reportar problema')));
   await page.evaluate(() => { window.__denyGPS = true; }); await click('Iniciar entrega');
   await page.waitForFunction(() => document.body.textContent.includes('Permita o acesso à localização')); assert.equal(startCalls,0);
   await page.evaluate(() => { window.__denyGPS = false; }); await click('Iniciar entrega');
   try { await page.waitForFunction(() => document.body.textContent.includes('A ação não foi confirmada')); } catch (e) { console.error({startCalls, body: await page.$eval('body',e=>e.innerText), errors}); throw e; } assert.equal(startCalls,1);
   await click('Iniciar entrega'); await page.waitForFunction(() => [...document.querySelectorAll('button')].some(b => b.textContent.includes('Marcar como entregue'))); assert.equal(startCalls,2); await fits('moving');
   await page.setViewport({ width, height: 540 }); await fits('short-viewport'); await page.setViewport({ width, height: 844 });
   // Confirmation is cancellable. Server failure keeps the delivery in progress.
   await click('Marcar como entregue'); await page.waitForSelector('dialog[open]'); await click('Ainda não'); assert.equal(completeCalls,0);
   await click('Marcar como entregue'); await click('Sim, foi entregue');
   await page.waitForFunction(() => document.body.textContent.includes('A ação não foi confirmada')); assert.equal(completeCalls,1); assert.equal(new URL(page.url()).pathname,'/driver/deliveries/7');
   await click('Marcar como entregue'); await click('Sim, foi entregue');
   await page.waitForFunction(() => new URL(location.href).pathname === '/driver/dashboard');
   assert.equal(completeCalls,2); assert.deepEqual(errors,[]);
   console.log(`PASS driver ${width}px: offline, accept conflict/retry, GPS denied, start failure/retry, confirmation cancel, completion failure/retry, navigation and short viewport`);
   // Available delivery details must allow acceptance, never premature start/completion.
   phase = 'available'; await page.goto(base + '/driver/deliveries/7', { waitUntil: 'domcontentloaded' });
   await page.waitForFunction(() => [...document.querySelectorAll('button')].some(b => b.textContent.trim() === 'Aceitar entrega'));
   assert(!await page.evaluate(() => [...document.querySelectorAll('button')].some(b => ['Iniciar entrega','Marcar como entregue'].includes(b.textContent.trim()))));
   await fits('available-details'); await context.close();
  }
 } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
