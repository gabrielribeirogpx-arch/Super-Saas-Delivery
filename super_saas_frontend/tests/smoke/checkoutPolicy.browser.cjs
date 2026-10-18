// Local dev-server regression with fixture API responses. Never charges money.
const puppeteer=require('puppeteer-core');const assert=require('node:assert/strict');
(async()=>{
 const browser=await puppeteer.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 const base=process.env.CHECKOUT_POLICY_TEST_BASE_URL||'http://127.0.0.1:3000';
 try{
  for(const scenario of ['free','unavailable','paid']){
   const page=await browser.newPage();let posts=0,sentMethod=null,recovered=false;
   await page.setBypassServiceWorker(true);await page.setViewport({width:430,height:900});
   await page.evaluateOnNewDocument(()=>{delete Navigator.prototype.serviceWorker;sessionStorage.clear();localStorage.setItem('mobile-storefront-cart:alpha',JSON.stringify([{id:'cart-1',menuItemId:1,name:'Burger',price:25,quantity:1,totalPrice:25,modifiers:[],note:''}]));});
   await page.setRequestInterception(true);page.on('request',r=>{
    const u=new URL(r.url()),send=(status,data)=>r.respond({status,contentType:'application/json',body:JSON.stringify(data)});
    if(u.pathname==='/manifest.webmanifest')return send(200,{});
    if(u.pathname==='/api/public/menu')return send(200,{slug:'alpha',tenant_id:1,tenant:{name:'Alpha',is_open:true,delivery_fee:0},public_settings:{theme:'white',primary_color:'#dc2626'},categories:[{id:1,name:'Burgers',items:[{id:1,name:'Burger',price_cents:2500}]}],items_without_category:[]});
    if(u.pathname==='/api/public/checkout-policy'){
     if(scenario==='unavailable'&&!recovered)return send(500,{});
     return send(200,scenario==='free'?{methods:[{id:'native_pix',label:'Pix online',available:false},{id:'native_card',label:'Cartão online',available:false}],message:'Esta loja não está recebendo pedidos online no momento.'}:{methods:[{id:'pix',label:'Pix direto da loja',available:true},{id:'money',label:'Dinheiro',available:true},{id:'card',label:'Cartão na entrega',available:true},{id:'native_pix',label:'Pix online',available:false}],message:null});
    }
    if(u.pathname==='/api/public/orders'&&r.method()==='POST'){posts++;sentMethod=JSON.parse(r.postData()).payment_method;return send(200,{order_number:1,daily_order_number:1,tracking_token:'fixture-token',total_cents:2500,status:'pending',payment_method:sentMethod,order_type:'pickup'});}
    if(u.pathname==='/api/public/order/fixture-token')return send(200,{order_number:1,status:'pending',total_cents:2500,payment_method:sentMethod,order_type:'pickup'});
    if(u.pathname.startsWith('/api/'))return send(200,{});return r.continue();
   });
   await page.goto(base+'/loja/alpha?preview=1',{waitUntil:'domcontentloaded'});
   await page.waitForFunction(()=>[...document.querySelectorAll('button')].some(b=>b.textContent.includes('Ver carrinho'))||document.querySelector('main[data-cart-bar-visible="true"]'));
   await page.evaluate(()=>window.dispatchEvent(new CustomEvent('storefront-open-cart')));
   await page.waitForFunction(()=>document.body.textContent.includes('Tipo de pedido'));
   const click=async text=>page.evaluate(t=>[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===t).click(),text);
   await click('RETIRADA');await click('Continuar');
   await page.waitForSelector('input[placeholder="(11) 99999-9999"]');await page.type('input[placeholder="(11) 99999-9999"]','11912345678');await click('Continuar');
   await page.waitForSelector('input[placeholder="Seu nome"]');await page.type('input[placeholder="Seu nome"]','Test Customer');await click('Continuar');
   await page.waitForFunction(()=>[...document.querySelectorAll('button')].some(b=>b.textContent==='Confirmar pedido'));
   const confirmDisabled=()=>page.evaluate(()=>[...document.querySelectorAll('button')].find(b=>b.textContent==='Confirmar pedido').disabled);
   if(scenario==='free'){
    await page.waitForSelector('input[value="native_pix"]');assert.equal(await confirmDisabled(),true);
    assert.equal(await page.$$eval('input[name="payment-method"]',xs=>xs.every(x=>x.disabled)),true);
    await page.evaluate(()=>{const b=[...document.querySelectorAll('button')].find(b=>b.textContent==='Confirmar pedido');b.disabled=false;b.click();});
    assert.equal(posts,0);
   }else{
    if(scenario==='unavailable'){
     await page.waitForFunction(()=>document.body.textContent.includes('Não foi possível carregar as formas'));
     assert.equal(await confirmDisabled(),true);assert.equal((await page.$$('input[name="payment-method"]')).length,0);
     recovered=true;await click('Tentar novamente');
    }
    await page.waitForSelector('input[value="card"]');await page.click('input[value="card"]');assert.equal(await confirmDisabled(),false);
    await click('Confirmar pedido');await page.waitForFunction(()=>document.body.textContent.includes('Pedido #1 recebido!'));
    assert.equal(posts,1);assert.equal(sentMethod,'card');
   }
   await page.close();console.log('Passed checkout policy browser scenario:',scenario);
  }
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
