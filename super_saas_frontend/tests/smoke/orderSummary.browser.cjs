// Run against a local Next.js dev server; all application API responses are fixtures.
const puppeteer = require('puppeteer-core');
const assert = require('node:assert/strict');
(async () => {
 const browser = await puppeteer.launch({executablePath:process.env.CHROMIUM_PATH || '/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 try {
  const page = await browser.newPage(); await page.setBypassServiceWorker(true);  await page.setViewport({width:430,height:900});
  let status = 'ready'; let reads = 0; const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.setRequestInterception(true);
  page.on('request',r=>{
   const u=new URL(r.url());
   if(u.pathname==='/sw.js') return r.respond({status:200,contentType:'application/javascript',body:'self.addEventListener("install",()=>self.skipWaiting());'});
   if(u.pathname==='/manifest.webmanifest') return r.respond({status:200,contentType:'application/json',body:'{}'});
   if(u.pathname==='/api/public/menu') return r.respond({status:200,contentType:'application/json',body:JSON.stringify({slug:'meuburger',tenant_id:1,tenant:{name:'Meu Burger',is_open:true,delivery_fee:0},public_settings:{theme:'white',primary_color:'#ff6a00'},categories:[{id:1,name:'Burgers',items:[{id:1,name:'Burger',price_cents:2990}]}],items_without_category:[]})});
   if(u.pathname==='/api/public/order/order-test-token') {reads++;return r.respond({status:200,contentType:'application/json',body:JSON.stringify({order_number:4,status,total_cents:2990,payment_method:'pix',order_type:'delivery',destination_lat:-23.5,destination_lng:-46.6,driver_lat:status==='delivering'?-23.51:null,driver_lng:status==='delivering'?-46.61:null})});}
   if(u.pathname.startsWith('/api/')) return r.respond({status:200,contentType:'application/json',body:'{}'});
   return r.continue();
  });
  await page.evaluateOnNewDocument(()=>{
   delete Navigator.prototype.serviceWorker;
   if(sessionStorage.getItem('fixture-seeded')) return;
   sessionStorage.setItem('fixture-seeded','true');
   sessionStorage.setItem('storefront:tracking-order:order-test-token',JSON.stringify({token:'order-test-token',tenant:'meuburger',orderNumber:4,totalCents:2990,subtotalCents:2990,deliveryFeeCents:0,paymentMethod:'pix',deliveryType:'delivery',createdAt:Date.now()}));
   sessionStorage.setItem('storefront:tracking-order:latest:meuburger','order-test-token');
   localStorage.setItem('mobile-storefront-cart:meuburger',JSON.stringify([{id:'new-cart',menuItemId:1,name:'Novo burger',price:15,quantity:1,totalPrice:15,modifiers:[],note:''}]));
  });
  await page.goto((process.env.ORDER_SUMMARY_TEST_BASE_URL || 'http://127.0.0.1:3000') + '/loja/meuburger?preview=1',{waitUntil:'domcontentloaded',timeout:120000});
  
  await page.waitForFunction(()=>[...document.querySelectorAll('button')].some(e=>e.textContent.includes('Acompanhar pedido #4')));
  const cart=await page.evaluate(()=>localStorage.getItem('mobile-storefront-cart:meuburger'));
  await page.evaluate(()=>[...document.querySelectorAll('button')].find(e=>e.textContent.includes('Acompanhar pedido #4')).click());
  await page.waitForFunction(()=>document.querySelector('[aria-current="step"]')?.textContent==='Pronto');
  assert.equal(new URL(page.url()).pathname,'/loja/meuburger');
  assert.equal(await page.$('a[href^="/pedido/order-test-token"]'),null);
  await page.reload({waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>document.querySelector('[aria-current="step"]')?.textContent==='Pronto');
  status='delivering';
  await page.waitForFunction(()=>document.querySelector('[aria-current="step"]')?.textContent?.includes('Saiu para entrega'),{timeout:10000});
  const mapLink=await page.$('a[href^="/pedido/order-test-token"]');
  assert.ok(mapLink,'O botão do mapa deve aparecer quando o pedido sai para entrega');
  assert.equal(await page.evaluate(()=>new URL(document.querySelector('a[href^="/pedido/order-test-token"]').href).searchParams.get('tenant')),'meuburger');
  assert.equal(await page.evaluate(()=>getComputedStyle([...document.querySelectorAll('button')].find(e=>e.textContent==='Voltar ao cardápio')).backgroundColor),'rgb(255, 106, 0)');
  await mapLink.click();
  await page.waitForFunction(()=>location.pathname==='/pedido/order-test-token',{timeout:15000});
  await page.goBack({waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>document.querySelector('[aria-current="step"]')?.textContent?.includes('Saiu para entrega'));
  status='delivered';
  await page.waitForFunction(()=>document.querySelector('[aria-current="step"]')?.textContent==='Entregue',{timeout:10000});
  await page.evaluate(()=>[...document.querySelectorAll('button')].find(e=>e.textContent==='Voltar ao cardápio').click());
  await page.waitForFunction(()=>!document.querySelector('[aria-current="step"]'));
  assert.equal(await page.evaluate(()=>localStorage.getItem('mobile-storefront-cart:meuburger')),cart);
  await page.reload({waitUntil:'domcontentloaded'});
  assert.equal(await page.evaluate(()=>!!document.querySelector('[aria-current="step"]')),false);
  assert.equal(errors.length,0,errors.join('\n'));
  console.log(JSON.stringify({passed:['same-page reopen','restores on F5','status updates without F5','map link appears during delivery','merchant color on action','map route opens','return stays closed on F5','new cart preserved','no browser errors'],reads}));
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
