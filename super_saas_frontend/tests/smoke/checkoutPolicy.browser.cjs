// Local dev-server regression with fixture API responses. Never charges money.
const puppeteer=require('puppeteer-core');const assert=require('node:assert/strict');
(async()=>{
 const browser=await puppeteer.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 const base=process.env.CHECKOUT_POLICY_TEST_BASE_URL||'http://127.0.0.1:3000';
 try{
  for(const scenario of ['free','unavailable','paid','signed-email','signed-phone','signed-no-address']){
   const page=await browser.newPage();let posts=0,sentMethod=null,sentOrder=null,recovered=false;
   const signedIn = scenario.startsWith('signed-');
   await page.setBypassServiceWorker(true);await page.setViewport({width:430,height:900});
   await page.evaluateOnNewDocument(()=>{delete Navigator.prototype.serviceWorker;sessionStorage.clear();localStorage.clear();localStorage.setItem('mobile-storefront-cart:alpha',JSON.stringify([{id:'cart-1',menuItemId:1,name:'Burger',price:25,quantity:1,totalPrice:25,modifiers:[],note:''}]));});
   await page.setRequestInterception(true);page.on('request',r=>{
    const u=new URL(r.url()),send=(status,data)=>r.respond({status,contentType:'application/json',body:JSON.stringify(data)});
    if(u.pathname==='/manifest.webmanifest')return send(200,{});
    if(u.pathname==='/api/public/menu')return send(200,{slug:'alpha',tenant_id:1,tenant:{name:'Alpha',is_open:true,delivery_fee:0},public_settings:{theme:'white',primary_color:'#dc2626'},categories:[{id:1,name:'Burgers',items:[{id:1,name:'Burger',price_cents:2500}]}],items_without_category:[]});
    if (u.pathname === '/api/public/customer-auth/checkout-profile') {
     assert.equal(u.searchParams.get('tenant'), 'alpha');
     if (!signedIn) return send(401, {});
     return send(200, {
      id: 8, name: 'Cliente da conta', phone: '+5511912345678',
      email: scenario === 'signed-email' ? 'cliente@example.test' : undefined,
      addresses: scenario === 'signed-no-address' ? [] : [
       { id: 1, zip: '01001000', street: 'Rua Alternativa', number: '8', neighborhood: 'Centro', city: 'São Paulo', state: 'SP' },
       { id: 2, zip: '01001000', street: 'Rua Padrão', number: '12', neighborhood: 'Centro', city: 'São Paulo', state: 'SP', is_default: true },
      ],
     });
    }
    if(u.pathname==='/api/public/checkout-policy'){
     if(scenario==='unavailable'&&!recovered)return send(500,{});
     return send(200,scenario==='free'?{methods:[],message:'Esta loja não está recebendo pedidos no momento.'}:{methods:[{id:'pix',label:'Pix',available:true},{id:'money',label:'Dinheiro',available:true},{id:'card',label:'Cartão',available:true},{id:'native_pix',label:'Pix online',available:false}],message:null});
    }
    if(u.pathname==='/api/public/orders'&&r.method()==='POST'){posts++;sentOrder=JSON.parse(r.postData());sentMethod=sentOrder.payment_method;return send(200,{order_number:1,daily_order_number:1,tracking_token:'fixture-token',total_cents:2500,status:'pending',payment_method:sentMethod,order_type:'pickup'});}
    if(u.pathname==='/api/public/order/fixture-token')return send(200,{order_number:1,status:'pending',total_cents:2500,payment_method:sentMethod,order_type:'pickup'});
    if(u.pathname.startsWith('/api/'))return send(200,{});return r.continue();
   });
   await page.goto(base+'/loja/alpha?preview=1',{waitUntil:'domcontentloaded'});
   await page.waitForFunction(()=>[...document.querySelectorAll('button')].some(b=>b.textContent.includes('Ver carrinho'))||document.querySelector('main[data-cart-bar-visible="true"]'));
   await page.evaluate(()=>window.dispatchEvent(new CustomEvent('storefront-open-cart')));
   await page.waitForFunction(()=>document.body.textContent.includes('Tipo de pedido'));
   const click=async text=>page.evaluate(t=>[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===t).click(),text);
   await page.waitForFunction(() => [...document.querySelectorAll('button')].some(b => b.textContent.trim() === 'Continuar' && !b.disabled));
   if (signedIn) {
    await click('Continuar');
    if (scenario === 'signed-no-address') {
     await page.waitForFunction(() => document.querySelector('h2#checkout-title')?.textContent === 'Endereço de entrega');
     assert.equal(await page.$('input[autocomplete="tel"]'), null);
     assert.equal(posts, 0);
     await page.close();
     console.log('Passed checkout policy browser scenario:', scenario);
     continue;
    }
    await page.waitForFunction(() => document.querySelector('h2#checkout-title')?.textContent === 'Endereço de entrega');
    assert.equal(await page.$('input[autocomplete="name"], input[autocomplete="tel"]'), null);
    assert.match(await page.$eval('[aria-labelledby="checkout-title"]', el => el.textContent), /Rua Padrão/);
    if (scenario === 'signed-phone') {
     await page.evaluate(() => [...document.querySelectorAll('button')].find(b => b.textContent.includes('Rua Alternativa')).click());
    }
    await page.type('textarea[placeholder="Ex.: chamar no interfone"]', 'Deixar na portaria');
    await click('Continuar');
   } else {
    await click('RETIRADA');await click('Continuar');
    await page.waitForSelector('input[placeholder="(11) 99999-9999"]');await page.type('input[placeholder="(11) 99999-9999"]','11912345678');await click('Continuar');
    await page.waitForSelector('input[placeholder="Seu nome"]');await page.type('input[placeholder="Seu nome"]','Test Customer');await click('Continuar');
   }
   await page.waitForFunction(()=>[...document.querySelectorAll('button')].some(b=>b.textContent==='Confirmar pedido'));
   assert.equal(await page.$('textarea[placeholder="Ex.: chamar no interfone"]'), null);
   const confirmDisabled=()=>page.evaluate(()=>[...document.querySelectorAll('button')].find(b=>b.textContent==='Confirmar pedido').disabled);
   if(scenario==='free'){
    await page.waitForFunction(()=>document.body.textContent.includes('Esta loja não está recebendo pedidos no momento.'));
    assert.equal(await confirmDisabled(),true);
    assert.equal((await page.$$('input[name="payment-method"]')).length,0);
    await page.evaluate(()=>{const b=[...document.querySelectorAll('button')].find(b=>b.textContent==='Confirmar pedido');b.disabled=false;b.click();});
    assert.equal(posts,0);
   }else{
    if(scenario==='unavailable'){
     await page.waitForFunction(()=>document.body.textContent.includes('Não foi possível carregar as formas'));
     assert.equal(await confirmDisabled(),true);assert.equal((await page.$$('input[name="payment-method"]')).length,0);
     recovered=true;await click('Tentar novamente');
    }
    await page.waitForSelector('input[value="card"]');await page.click('input[value="card"]');assert.equal(await confirmDisabled(),false);
    assert.equal((await page.$$('input[value="native_pix"]')).length,0);
    await click('Confirmar pedido');await page.waitForFunction(()=>document.body.textContent.includes('Pedido #1 recebido!'));
    assert.equal(posts,1);assert.equal(sentMethod,'card');
    if (signedIn) {
     assert.equal(sentOrder.customer_name, 'Cliente da conta');
     assert.equal(sentOrder.customer_phone, '+5511912345678');
     assert.equal(sentOrder.reference, 'Deixar na portaria');
     assert.equal(sentOrder.delivery_address.street, scenario === 'signed-email' ? 'Rua Padrão' : 'Rua Alternativa');
     assert.equal(sentOrder.customer_email, scenario === 'signed-email' ? 'cliente@example.test' : undefined);
    } else {
     assert.equal(sentOrder.reference, undefined);
    }
   }
   await page.close();console.log('Passed checkout policy browser scenario:',scenario);
  }
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
