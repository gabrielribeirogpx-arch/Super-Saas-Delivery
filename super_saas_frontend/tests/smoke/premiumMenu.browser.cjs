// Public menu interactions against fixtures, without touching a live store.
const puppeteer = require('puppeteer-core');
const assert = require('node:assert/strict');
const base = process.env.MENU_TEST_BASE_URL || 'http://127.0.0.1:3057';
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
        if(url.pathname === '/api/public/menu') return send({slug:url.searchParams.get('slug') || 'alpha',tenant_id:1,tenant:{name:'Meu Burger',is_open:true,delivery_fee:5},public_settings:{theme:'white',primary_color:'#dc2626'},categories:[{id:1,name:'Burgers',items:[{id:1,name:'Burger da casa',description:'Pão macio, carne na brasa e queijo derretido.',price_cents:2990,modifier_groups:[{id:1,name:'Ponto da carne',required:true,min_selection:1,max_selection:1,options:[{id:1,name:'Ao ponto',price_delta:0}]}]},{id:2,name:'Indisponível',is_active:false,price_cents:2000}]},{id:2,name:'Bebidas',items:[{id:3,name:'Limonada',description:'Preparada na hora.',price_cents:900}]}],items_without_category:[]});
        if(url.pathname === '/api/public/checkout-policy') return send({methods:[{id:'pix',label:'Pix',available:true},{id:'card',label:'Cartão com a loja',available:true}]});
        if(url.pathname.startsWith('/api/') || url.pathname === '/manifest.webmanifest') return send({});
        if(!['127.0.0.1','localhost'].includes(url.hostname)) return request.abort();
        request.continue();
      });
      await page.goto(base+'/loja/alpha?preview=1',{waitUntil:'domcontentloaded',timeout:120000});
      await page.waitForSelector('input[aria-label="Buscar no cardápio"]');
      await page.waitForFunction(() => document.body.textContent.includes('Burger da casa'));
      await page.click('article[role="button"]');
      await page.waitForSelector('[aria-labelledby="item-detail-title"]');
      assert(await page.evaluate(() => [...document.querySelectorAll('button')].some(b => b.disabled && b.textContent.includes('Selecione as opções'))));
      await page.evaluate(() => [...document.querySelectorAll('button')].find(b=>b.textContent.trim()==='Ao ponto').click());
      await page.click('button[aria-label="Aumentar quantidade"]');
      await page.type('#item-note','Sem cebola');
      if(width===390) await page.screenshot({path:'/tmp/premium-product.png',fullPage:false});
      await page.evaluate(() => [...document.querySelectorAll('button')].find(b=>b.textContent.includes('Adicionar ·')).click());
      await page.waitForFunction(() => !document.querySelector('[aria-labelledby="item-detail-title"]'));
      assert(await page.evaluate(() => {
        const cart=JSON.parse(localStorage.getItem('mobile-storefront-cart:alpha'));
        return cart[0].quantity===2 && cart[0].note==='Sem cebola' && cart[0].modifiers[0].optionName==='Ao ponto';
      }));
      await page.evaluate(() => window.dispatchEvent(new CustomEvent('storefront-open-cart')));
      await page.waitForSelector('[aria-labelledby="checkout-title"]');
      assert.equal(await page.$eval('[aria-labelledby="checkout-title"]', el => getComputedStyle(el.parentElement).getPropertyValue('--checkout-brand').trim()), '#dc2626');
      await page.evaluate(() => Promise.all(document.getAnimations().map(a=>a.finished.catch(()=>{}))));
      if(width===390) await page.screenshot({path:'/tmp/premium-checkout.png',fullPage:false});
      assert(await page.$eval('[aria-labelledby="checkout-title"]',el=>el.scrollWidth<=el.clientWidth));
      await page.click('[aria-label="Sugestões para o pedido"] button[aria-label="Adicionar Limonada"]');
      await page.waitForFunction(() => JSON.parse(localStorage.getItem('mobile-storefront-cart:alpha')).some(item => item.name === 'Limonada'));
      assert(await page.evaluate(() => JSON.parse(localStorage.getItem('mobile-storefront-cart:alpha')).some(item => item.name === 'Limonada')));
      if(width===390) {
        await page.click('button[aria-label="Fechar checkout"]');
        await page.click('button[aria-label="Alternar tema"]');
        await page.waitForFunction(() => document.querySelector('main[data-theme]')?.dataset.theme === 'dark');
        assert.equal(await page.evaluate(() => localStorage.getItem('menu-theme:alpha')), 'dark');
        await page.goto(base+'/loja/beta?preview=1',{waitUntil:'domcontentloaded'});
        await page.waitForFunction(() => document.querySelector('main[data-theme]')?.dataset.theme === 'white');
        await page.waitForFunction(() => localStorage.getItem('menu-theme:beta') === 'white');
        assert.equal(await page.evaluate(() => localStorage.getItem('menu-theme:beta')), 'white');
      }
      console.log('PASS product selection, required modifier, quantity, note and checkout at '+width+'px');
      await page.close();
    }
  } finally { await browser.close(); }
})().catch(error => {console.error(error);process.exitCode=1;});
