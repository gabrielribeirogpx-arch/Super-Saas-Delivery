// Public menu interactions against fixtures, without touching a live store.
const puppeteer = require('puppeteer-core');
const assert = require('node:assert/strict');
const base = process.env.MENU_TEST_BASE_URL || 'http://127.0.0.1:3056';
(async () => {
  const browser = await puppeteer.launch({executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium', headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
  try {
    for (const width of [320,390]) {
      const page = await browser.newPage();
      await page.setViewport({width,height:900});
      await page.setBypassServiceWorker(true);
      await page.evaluateOnNewDocument(() => { delete Navigator.prototype.serviceWorker; localStorage.clear(); sessionStorage.clear(); });
      await page.setRequestInterception(true);
      page.on('request', request => {
        const url = new URL(request.url());
        const send = data => request.respond({status:200,contentType:'application/json',body:JSON.stringify(data)});
        if(url.pathname === '/api/public/menu') return send({slug:'alpha',tenant_id:1,tenant:{name:'Meu Burger',is_open:true,delivery_fee:5},public_settings:{theme:'white',primary_color:'#dc2626'},categories:[{id:1,name:'Burgers',items:[{id:1,name:'Burger da casa',description:'Pão macio, carne na brasa e queijo derretido.',price_cents:2990},{id:2,name:'Indisponível',is_active:false,price_cents:2000}]},{id:2,name:'Bebidas',items:[{id:3,name:'Limonada',description:'Preparada na hora.',price_cents:900}]}],items_without_category:[]});
        if(url.pathname === '/api/public/customer-auth/me') return request.respond({status:401,contentType:'application/json',body:JSON.stringify({detail:'Not authenticated'})});
        if(url.pathname.startsWith('/api/') || url.pathname === '/manifest.webmanifest') return send({});
        if(!['127.0.0.1','localhost'].includes(url.hostname)) return request.abort();
        request.continue();
      });
      await page.goto(base+'/loja/alpha?preview=1',{waitUntil:'domcontentloaded',timeout:120000});
      await page.waitForSelector('input[aria-label="Buscar no cardápio"]');
      await page.waitForFunction(() => document.body.textContent.includes('Burger da casa'));
      const nav = 'nav[aria-label="Navegação da loja"]';
      const clickTab = async text => {
        await page.waitForSelector(nav);
        await page.evaluate(({nav,text}) => [...document.querySelector(nav).querySelectorAll('a,button')].find(el => el.lastElementChild?.textContent.trim() === text).click(),{nav,text});
      };
      await clickTab('Pedidos');
      await page.waitForSelector('#customer-phone');
      assert.equal(await page.$$eval(nav,els=>els.length),1);
      assert(await page.$eval(nav,el=>getComputedStyle(el).display !== 'none'));
      assert(new URL(page.url()).searchParams.get('tenant') === 'alpha');
      await clickTab('Início');
      await page.waitForSelector('button[aria-label="Adicionar Burger da casa"]');
      await page.click('button[aria-label="Adicionar Burger da casa"]');
      await clickTab('Conta');
      await page.waitForSelector('#customer-phone');
      await clickTab('Carrinho');
      await page.waitForFunction(() => document.body.textContent.includes('Tipo de pedido'));
      await page.goto(base+'/account/verify?tenant=alpha');
      await page.waitForSelector('input[aria-label="Código de acesso"]');
      assert.equal(await page.$$eval(nav,els=>els.length),1);
      await clickTab('Início');
      await page.waitForSelector('button[aria-label="Adicionar Burger da casa"]');
      console.log('PASS persistent navigation through login, verify, home and cart at '+width+'px');
      await page.close();
    }
  } finally { await browser.close(); }
})().catch(error => {console.error(error);process.exitCode=1;});
