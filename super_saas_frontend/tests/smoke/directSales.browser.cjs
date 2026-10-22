const puppeteer = require('puppeteer-core');
const assert = require('node:assert/strict');
const base = process.env.SALES_TEST_BASE_URL || 'http://127.0.0.1:3013';
const config = { ready: true, site_key: 'synthetic-site-key', terms_url: 'https://legal.example/terms', privacy_url: 'https://legal.example/privacy', terms_version: '2026-10', support_email: 'support@example.com', offers: [
  { code:'essential',name:'Essencial',price_cents:9990,features:[{code:'orders_monthly',enabled:true,limit:300}] },
  { code:'operation',name:'Operação',price_cents:17990,features:[{code:'orders_monthly',enabled:true,limit:1500}] },
  { code:'pro',name:'Pro',price_cents:29990,features:[{code:'orders_monthly',enabled:true,limit:5000}] },
] };
(async () => {
 const browser = await puppeteer.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 try {
  async function pageFor(settings = config) {
   const page = await browser.newPage(); const seen = { meta:0, posts:[], destination:null };
   await page.setBypassServiceWorker(true);
   await page.evaluateOnNewDocument(() => { delete Navigator.prototype.serviceWorker; window.__pixelEvents=[]; });
   await page.setRequestInterception(true);
   page.on('request', req => {
    const u = new URL(req.url());
    const json = value => req.respond({status:200,contentType:'application/json',body:JSON.stringify(value)});
    if (u.hostname === 'connect.facebook.net') { seen.meta++; return req.respond({status:200,contentType:'text/javascript',body:`window.__pixelEvents.push(...window.fbq.queue); window.fbq.callMethod=(...args)=>window.__pixelEvents.push(args);`}); }
    if (u.hostname === 'challenges.cloudflare.com') return req.respond({status:200,contentType:'text/javascript',body:`window.turnstile={render(el,options){ window.__captchaCallback=options.callback; el.innerHTML='<button type="button" id="mock-captcha">Verificar</button>'; el.querySelector('button').onclick=()=>options.callback('one-use-token'); return '1'; },remove(){}};`});
    if (u.pathname === '/api/onboarding/sales-config') return json(settings);
    if (u.pathname === '/api/onboarding/tenant') {
      seen.posts.push(JSON.parse(req.postData()));
      return req.respond({status:201,contentType:'application/json',body:JSON.stringify({tenant_id:3,slug:'test-restaurant',business_name:'Restaurant',admin_email:'test@example.com',subscription_required:true})});
    }
    if (u.hostname === 'test-restaurant.fomizero.com.br') { seen.destination = u.href; return req.abort(); }
    if (u.origin !== new URL(base).origin) return req.abort();
    if (u.pathname.startsWith('/api/')) return json({});
    return req.continue();
   });
   return {page,seen};
  }
  {
   const {page,seen} = await pageFor();
   await page.goto(base+'/assine',{waitUntil:'networkidle0'});
   await page.waitForSelector('a[href="/onboarding?plan=essential"]');
   assert.equal(seen.meta,0,'must not load pixel before consent');
   await page.evaluate(()=>[...document.querySelectorAll('button')].find(e=>e.textContent==='Recusar publicidade').click());
   assert.equal(seen.meta,0);
   await page.evaluate(()=>[...document.querySelectorAll('button')].find(e=>e.textContent==='Privacidade dos anúncios').click());
   await page.evaluate(()=>[...document.querySelectorAll('button')].find(e=>e.textContent==='Aceitar publicidade').click());
   await page.waitForFunction(()=>window.__pixelEvents.some(e=>e[1]==='PageView'));
   assert.equal(seen.meta,1);
   assert.equal(await page.evaluate(()=>window.__pixelEvents.filter(e=>e[1]==='PageView').length),1);
   for (const width of [360,390,1366]) { await page.setViewport({width,height:850}); assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)); }
   await page.goto(base+'/assine?payment=approved',{waitUntil:'networkidle0'});
   assert.equal(await page.evaluate(()=>window.__pixelEvents.filter(e=>e[1]==='Purchase').length),0,'return URL cannot count a sale');
   await page.evaluate(()=>[...document.querySelectorAll('button')].find(e=>e.textContent==='Privacidade dos anúncios').click());
   await page.evaluate(()=>[...document.querySelectorAll('button')].find(e=>e.textContent==='Recusar publicidade').click());
   assert.ok(await page.evaluate(()=>window.__pixelEvents.some(e=>e[0]==='consent'&&e[1]==='revoke')));
   await page.close(); console.log('PASS landing desktop/mobile; consent refusal/grant/revoke; no false Purchase');
  }
  {
   const {page,seen} = await pageFor();
   await page.goto(base+'/onboarding?plan=operation',{waitUntil:'networkidle0'});
   await page.type('input[placeholder="Nome do restaurante"]','Restaurant');
   await page.evaluate(()=>[...document.querySelectorAll('button')].find(e=>e.textContent==='Continuar').click());
   await page.waitForSelector('input[type="password"]');
   await page.type('input[placeholder="Nome do administrador"]','Owner');
   await page.type('input[type="email"]','test@example.com'); await page.type('input[type="password"]','synthetic-password');
   assert.equal(await page.$eval('button[type="submit"]',e=>e.disabled),true);
   await page.click('input[type="checkbox"]');
   assert.equal(await page.$eval('button[type="submit"]',e=>e.disabled),true,'captcha still required');
   await page.waitForSelector('#mock-captcha'); await page.click('#mock-captcha');
   await page.waitForFunction(()=>!document.querySelector('button[type="submit"]').disabled);
   await page.evaluate(()=>document.querySelector('form').requestSubmit());
   await page.waitForFunction(()=>document.body.textContent.includes('ERR') || !document.querySelector('form'),{timeout:2000}).catch(()=>{});
   assert.equal(seen.posts.length,1); assert.equal(seen.posts[0].accept_terms,true); assert.equal(seen.posts[0].captcha_token,'one-use-token');
   assert.equal(seen.posts[0].terms_version,'2026-10');
   assert.equal(new URL(seen.destination).searchParams.get('redirect'),'/subscriptions?plan=operation');
   assert.equal(seen.meta,0,'refusing advertising does not block registration');
   await page.close(); console.log('PASS public onboarding requires terms + captcha; preserves selected plan; no advertising required');
  }
  {
   const {page,seen} = await pageFor({...config,ready:false,site_key:''});
   await page.goto(base+'/assine',{waitUntil:'networkidle0'});
   assert.equal(await page.$('a[href^="/onboarding?plan="]'),null);
   await page.goto(base+'/onboarding',{waitUntil:'networkidle0'});
   await page.type('input[placeholder="Nome do restaurante"]','Restaurant');
   await page.evaluate(()=>[...document.querySelectorAll('button')].find(e=>e.textContent==='Continuar').click());
   await page.waitForSelector('button[type="submit"]');
   assert.equal(await page.$eval('button[type="submit"]',e=>e.disabled),true); assert.equal(seen.posts.length,0);
   await page.close(); console.log('PASS missing sales configuration fails closed');
  }
 } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
