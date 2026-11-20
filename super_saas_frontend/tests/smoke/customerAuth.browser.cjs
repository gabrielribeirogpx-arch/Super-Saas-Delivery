// Fixture-only browser regression. Start a local Next.js dev server first.
const puppeteer = require('puppeteer-core');
const assert = require('node:assert/strict');
(async () => {
 const browser = await puppeteer.launch({executablePath:process.env.CHROMIUM_PATH || '/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 try {
  const page=await browser.newPage(); const base=process.env.CUSTOMER_AUTH_TEST_BASE_URL || 'http://127.0.0.1:3000';
  let signedIn=false, providerReady=false; const apiTenants=[], codeRequests=[];
  await page.setBypassServiceWorker(true);
  await page.evaluateOnNewDocument(()=>{delete Navigator.prototype.serviceWorker;});
  await page.setRequestInterception(true);
  page.on('request',r=>{
   const u=new URL(r.url()); const send=(status,data)=>r.respond({status,contentType:'application/json',body:JSON.stringify(data)});
   if(u.pathname==='/manifest.webmanifest') return send(200,{});
   if(u.pathname.startsWith('/api/public/customer-auth/')) {
    apiTenants.push(u.searchParams.get('tenant'));
    if(u.pathname.endsWith('/me')) return signedIn?send(200,{name:'Customer Name',verification_method:'email',email_masked:'c***@example.com',phone_masked:'+55******11'}):send(401,{detail:'Confirme seu e-mail'});
    if(u.pathname.endsWith('/request-email-code')) {codeRequests.push(JSON.parse(r.postData()));return providerReady?send(200,{ok:true}):send(503,{detail:'Acesso por e-mail temporariamente indisponível.'});}
    if(u.pathname.endsWith('/verify-email-code')) {signedIn=true;return send(200,{ok:true});}
    if(u.pathname.endsWith('/orders')) return signedIn?send(200,[{order_number:1,tracking_token:'own-token',status:'PRONTO',total_cents:2990,payment_method:'pix',delivery_type:'delivery'}]):send(401,{detail:'Confirme seu e-mail'});
    if(u.pathname.endsWith('/logout')) {signedIn=false;return send(200,{ok:true});}
   }
   if(u.pathname.startsWith('/api/')) return send(200,{});
   return r.continue();
  });
  await page.goto(base+'/account/orders?tenant=alpha',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>location.pathname==='/account/login');
  await page.waitForSelector('#customer-email');
  await page.type('#customer-name','Customer Name'); await page.type('#customer-phone','11933334444');
  await page.type('#customer-email','customer@example.com'); await page.click('input[type=checkbox]');
  await page.evaluate(()=>[...document.querySelectorAll('button')].find(e=>e.textContent==='Confirmar e-mail e criar conta').click());
  await page.waitForSelector('[role=alert]');
  assert.match(await page.$eval('[role=alert]',e=>e.textContent),/indisponível/);
  assert.equal(new URL(page.url()).pathname,'/account/login');
  assert.equal(await page.evaluate(()=>sessionStorage.getItem('customer-auth-email:alpha')),null);
  providerReady=true;
  await page.evaluate(()=>[...document.querySelectorAll('button')].find(e=>e.textContent==='Confirmar e-mail e criar conta').click());
  await page.waitForSelector('input[autocomplete="one-time-code"]');
  assert.equal(codeRequests[1].name,'Customer Name'); assert.equal(codeRequests[1].phone,'11933334444');
  assert.equal(new URL(page.url()).searchParams.get('tenant'),'alpha');
  await page.evaluate(()=>{sessionStorage.setItem('storefront:tracking-order:previous','private');localStorage.setItem('mobile-storefront-cart:alpha','new-cart');});
  await page.type('input[autocomplete="one-time-code"]','123456');
  await page.evaluate(()=>[...document.querySelectorAll('button')].find(e=>e.textContent==='Confirmar código').click());
  await page.waitForFunction(()=>document.body.textContent.includes('Pedido #1'));
  assert.equal(await page.evaluate(()=>sessionStorage.getItem('storefront:tracking-order:previous')),null);
  assert.equal(new URL(page.url()).pathname,'/account/orders');
  await page.goto(base+'/account?tenant=alpha',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>document.body.textContent.includes('E-mail verificado'));
  await page.evaluate(()=>{sessionStorage.setItem('storefront:tracking-order:own-token','private');sessionStorage.setItem('storefront:order-summary-open:alpha','own-token');localStorage.setItem('service-delivery:alpha:customer-orders','["old"]');});
  await page.evaluate(()=>[...document.querySelectorAll('button')].find(e=>e.textContent==='Sair').click());
  await page.waitForFunction(()=>location.pathname==='/account/login');
  assert.equal(await page.evaluate(()=>sessionStorage.getItem('storefront:order-summary-open:alpha')),null);
  assert.equal(await page.evaluate(()=>localStorage.getItem('service-delivery:alpha:customer-orders')),null);
  assert.equal(await page.evaluate(()=>localStorage.getItem('mobile-storefront-cart:alpha')),'new-cart');
  await page.evaluate(()=>[...document.querySelectorAll('button')].find(e=>e.textContent==='Já tenho conta').click());
  await page.type('#customer-email','customer@example.com');
  await page.evaluate(()=>[...document.querySelectorAll('button')].find(e=>e.textContent==='Receber código para entrar').click());
  await page.waitForSelector('input[autocomplete="one-time-code"]');
  assert.equal(codeRequests[2].email,'customer@example.com');
  assert.equal(codeRequests[2].name,undefined);
  assert.equal(codeRequests[2].phone,undefined);
  assert.ok(apiTenants.length>0 && apiTenants.every(t=>t==='alpha'),JSON.stringify(apiTenants));
  console.log('Passed: email history login, unavailable-provider message, OTP UI with fixtures, tenant context, account switch cleanup, logout cleanup and cart preservation.');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
