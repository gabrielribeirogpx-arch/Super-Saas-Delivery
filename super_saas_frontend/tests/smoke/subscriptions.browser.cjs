// Browser fixtures only. No provider account, charge or subscription is contacted.
const puppeteer=require('puppeteer-core');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await puppeteer.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 const base=process.env.SUBSCRIPTIONS_TEST_BASE_URL||'http://127.0.0.1:3004';
 try{
  for(const scenario of ['checkout','cancel','disabled','forbidden','error']){
   const page=await browser.newPage();await page.setBypassServiceWorker(true);await page.evaluateOnNewDocument(()=>{delete Navigator.prototype.serviceWorker;});
   await page.setViewport({width:scenario==='cancel'?430:1365,height:900});
   let posts=0,reads=0,navigation=null;
   const errors=[];page.on('pageerror',e=>errors.push(e.message));
   const current={enabled:scenario!=='disabled',provider:scenario==='cancel'?'hotmart':null,status:scenario==='cancel'?'active':'not_contracted',plan_name:scenario==='cancel'?'Essencial':null,period_end:'2026-11-19T12:00:00Z',cancel_at_period_end:false,cancel_pending:false,can_cancel:scenario==='cancel',can_checkout:scenario==='checkout',checkout_pending:false,offers:[{code:'essential',name:'Essencial',price_cents:9990,features:[{code:'orders_monthly',enabled:true,limit:300}]}],events:[]};
   await page.setRequestInterception(true);
   page.on('request',async req=>{
    const u=new URL(req.url());const send=(status,data)=>req.respond({status,contentType:'application/json',body:JSON.stringify(data)});
    if(u.hostname==='pay.hotmart.com'){navigation=u.href;return req.abort();}
    if(u.pathname==='/api/admin/auth/me')return send(200,{id:1,tenant_id:1,name:'Owner',role:scenario==='forbidden'?'operator':'owner',active:true});
    if(u.pathname==='/api/admin/billing/subscription'){reads++;return send(scenario==='error'?503:200,current);}
    if(u.pathname==='/api/admin/billing/subscription/checkout'){
     posts++;assert.equal(req.headers()['x-billing-action'],'1');assert.deepEqual(JSON.parse(req.postData()),{plan_code:'essential'});
     await new Promise(r=>setTimeout(r,250));return send(200,{checkout_url:'https://pay.hotmart.com/A123?off=offer&sck=fixture-opaque',expires_at:'2026-10-26T12:00:00Z'});
    }
    if(u.pathname==='/api/admin/billing/subscription/cancel'){
     posts++;assert.equal(req.headers()['x-billing-action'],'1');current.cancel_pending=true;current.can_cancel=false;
     await new Promise(r=>setTimeout(r,250));return send(200,current);
    }
    if(u.pathname.startsWith('/api/'))return send(200,{});
    if(u.origin!==new URL(base).origin)return req.abort();
    return req.continue();
   });
   await page.goto(base+'/subscriptions',{waitUntil:'domcontentloaded'});
   const click=text=>page.evaluate(t=>{const b=[...document.querySelectorAll('button')].find(x=>x.textContent.trim()===t);if(!b)throw Error('Missing button '+t);b.click();},text);
   if(scenario==='forbidden'){
    await page.waitForFunction(()=>document.body.textContent.includes('Acesso'));assert.equal(reads,0);
   }else if(scenario==='disabled'){
    await page.waitForFunction(()=>document.body.textContent.includes('contratação online ainda não está disponível'));assert.equal(await page.$('dialog[open]'),null);assert.equal(posts,0);
   }else if(scenario==='error'){
    await page.waitForFunction(()=>document.body.textContent.includes('Não foi possível consultar sua assinatura'));assert.equal(posts,0);
   }else if(scenario==='cancel'){
    await page.waitForFunction(()=>document.body.textContent.includes('Cancelar renovação'));
    await click('Cancelar renovação');await page.waitForSelector('dialog[open]');
    assert.match(await page.$eval('dialog',el=>el.textContent),/não solicita reembolso/);
    await click('Voltar');assert.equal(posts,0);
    await click('Cancelar renovação');await page.waitForSelector('dialog[open]');
    await page.evaluate(()=>{const b=[...document.querySelectorAll('dialog button')].find(x=>x.textContent==='Confirmar cancelamento');b.click();b.click();});
    await page.waitForFunction(()=>document.body.textContent.includes('Solicitação registrada'));
    assert.equal(posts,1);assert.match(await page.$eval('body',el=>el.textContent),/confirmação da Hotmart está pendente/);
    assert.equal(await page.$('dialog[open]'),null);
    await page.screenshot({path:'/workspace/work/hotmart-subscription-mobile.png',fullPage:true});
   }else{
    await page.waitForFunction(()=>document.body.textContent.includes('Assinar Essencial'));
    await page.evaluate(()=>{const b=[...document.querySelectorAll('button')].find(x=>x.textContent==='Assinar Essencial');b.click();b.click();});
    const deadline=Date.now()+10000;while(!navigation&&Date.now()<deadline)await new Promise(r=>setTimeout(r,50));
    assert.equal(posts,1);assert.match(navigation,/^https:\/\/pay.hotmart.com\/A123/);
   }
   assert.deepEqual(errors,[]);await page.close();console.log('PASS subscription '+scenario);
  }
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
