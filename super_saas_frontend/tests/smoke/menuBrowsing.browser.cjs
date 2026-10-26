// Public menu interactions against fixtures, without touching a live store.
const puppeteer = require('puppeteer-core');
const assert = require('node:assert/strict');
const base = process.env.MENU_TEST_BASE_URL || 'http://127.0.0.1:3055';
(async () => {
  const browser = await puppeteer.launch({executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium', headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
  try {
    for (const width of [320,390,1366]) {
      const page = await browser.newPage();
      await page.setViewport({width,height:900});
      await page.setBypassServiceWorker(true);
      await page.evaluateOnNewDocument(() => { delete Navigator.prototype.serviceWorker; localStorage.clear(); sessionStorage.clear(); });
      await page.setRequestInterception(true);
      page.on('request', request => {
        const url = new URL(request.url());
        const send = data => request.respond({status:200,contentType:'application/json',body:JSON.stringify(data)});
        if(url.pathname === '/api/public/menu') return send({slug:'alpha',tenant_id:1,tenant:{name:'Meu Burger',is_open:true,delivery_fee:5},public_settings:{theme:'white',primary_color:'#dc2626'},categories:[{id:1,name:'Burgers',items:[{id:1,name:'Burger da casa',description:'Pão macio, carne na brasa e queijo derretido.',price_cents:2990},{id:2,name:'Indisponível',is_active:false,price_cents:2000}]},{id:2,name:'Bebidas',items:[{id:3,name:'Limonada',description:'Preparada na hora.',price_cents:900}]}],items_without_category:[]});
        if(url.pathname.startsWith('/api/') || url.pathname === '/manifest.webmanifest') return send({});
        if(!['127.0.0.1','localhost'].includes(url.hostname)) return request.abort();
        request.continue();
      });
      await page.goto(base+'/loja/alpha?preview=1',{waitUntil:'domcontentloaded',timeout:120000});
      await page.waitForSelector('input[aria-label="Buscar no cardápio"]');
      await page.waitForFunction(() => document.body.textContent.includes('Burger da casa'));
      assert(!await page.evaluate(() => document.body.textContent.includes('Indisponível')));
      await page.evaluate(() => [...document.querySelectorAll('button')].find(button => button.querySelector('h3')?.textContent === 'Limonada')?.click());
      await page.waitForFunction(() => JSON.parse(localStorage.getItem('mobile-storefront-cart:alpha') || '[]').some(item => item.name === 'Limonada'));
      assert.equal(await page.$$eval('[aria-labelledby="item-detail-title"]', elements => elements.length), 0);
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      const click = text => page.evaluate(text => [...document.querySelectorAll('button')].find(b => b.textContent.trim() === text).click(),text);
      await click('Burgers');
      await page.type('input[aria-label="Buscar no cardápio"]','Limonada');
      await page.waitForFunction(() => [...document.querySelectorAll('h3')].some(el => el.textContent === 'Limonada'));
      assert(!await page.evaluate(() => [...document.querySelectorAll('h3')].some(el => el.textContent === 'Burger da casa')));
      await page.click('button[aria-label="Limpar busca"]');
      assert.equal(await page.evaluate(() => document.activeElement.getAttribute('aria-label')),'Buscar no cardápio');
      await page.type('input[aria-label="Buscar no cardápio"]','zzzzzz');
      await page.waitForSelector('[role="status"]');
      await click('Ver todo o cardápio');
      await page.click('button[aria-label="Adicionar Burger da casa"]');
      await page.waitForFunction(() => document.querySelector('button[aria-label="Adicionar Burger da casa"]').textContent.includes('1'));
      await page.evaluate(() => Promise.all(document.getAnimations().map(animation => animation.finished.catch(() => {}))));
      if(width === 390) await page.screenshot({path:'/tmp/menu-premium-mobile.png',fullPage:true});
      await page.click('button[aria-label="Alternar tema"]');
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      const lightHero = await page.evaluate(() => ({
        theme: document.querySelector('main[data-theme]').dataset.theme,
        nameColor: getComputedStyle(document.querySelector('h1')).color,
        pageColor: getComputedStyle(document.querySelector('main[data-theme]')).backgroundColor,
        heroHeight: Math.round(document.querySelector('header').getBoundingClientRect().height),
      }));
      assert.equal(lightHero.theme, 'white');
      assert.equal(lightHero.nameColor, 'rgb(40, 32, 23)');
      assert.equal(lightHero.pageColor, 'rgb(248, 245, 239)');
      assert.equal(lightHero.heroHeight, width < 768 ? 278 : 360);
      await new Promise(resolve => setTimeout(resolve, 450));
      if (width === 390) await page.screenshot({path:'/tmp/menu-light.png',fullPage:true});
      console.log('PASS browsing, global search, clear, empty state, cart and themes at '+width+'px');
      await page.close();
    }
  } finally { await browser.close(); }
})().catch(error => {console.error(error);process.exitCode=1;});
