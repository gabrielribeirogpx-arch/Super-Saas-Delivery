// Local fixtures only. No bank, processor, or live backend is contacted.
const puppeteer=require('puppeteer-core');const assert=require('node:assert/strict');
(async()=>{
 const browser=await puppeteer.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 const base=process.env.MANUAL_PAYMENTS_TEST_BASE_URL||'http://127.0.0.1:3000';
 try{
  for(const scenario of ['cancel','refund','refund-error']){
   const page=await browser.newPage();await page.setBypassServiceWorker(true);
      await page.evaluateOnNewDocument(() => { delete Navigator.prototype.serviceWorker; });await page.setViewport({width:scenario==='cancel'?1365:430,height:900});
   let state=scenario==='cancel'?'pending':'paid',posts=0,reason=null;
   const originalPaid=state==='paid';
   await page.setRequestInterception(true);page.on('request',async r=>{
    const u=new URL(r.url()),send=(status,data)=>r.respond({status,contentType:'application/json',body:JSON.stringify(data)});
    if(u.pathname==='/api/admin/auth/me')return send(200,{id:1,tenant_id:1,name:'Gabriel',role:'owner',active:true});
    if(u.pathname==='/api/finance/manual-payments'){
     const terminal=['refunded','canceled'].includes(state);
     const item={id:9,order_id:9,order_number:4,method:'cash',amount_cents:2990,status:state,order_status:'DELIVERED',created_at:new Date().toISOString(),paid_at:originalPaid?new Date().toISOString():null,confirmed_by:originalPaid?'Gabriel':null,can_confirm:state==='pending',can_cancel:state==='pending',can_refund:state==='paid',last_adjustment:terminal?{status:state,reason,recorded_at:new Date().toISOString(),recorded_by:'Gabriel'}:null};
     const visible=u.searchParams.get('status')===state;
     return send(200,{items:visible?[item]:[],total:visible?1:0,pending_cents:state==='pending'?2990:0,paid_cents:state==='paid'?2990:0,canceled_cents:state==='canceled'?2990:0,refunded_cents:state==='refunded'?2990:0});
    }
    if(u.pathname==='/api/finance/cash/summary')return send(200,{total_in_cents:originalPaid?2990:0,total_out_cents:state==='refunded'?2990:0,net_cents:originalPaid&&state!=='refunded'?2990:0,by_category:{}});
    if(u.pathname==='/api/finance/cash/movements')return send(200,[]);
    if(u.pathname==='/api/orders/9/payments/9/status'){
     posts++;const data=JSON.parse(r.postData());assert.equal(data.status,scenario==='cancel'?'canceled':'refunded');assert.equal(data.reason,'Solicitação do cliente <img src=x onerror=alert(1)>');assert.equal(Object.keys(data).length,2);
     if(scenario==='refund-error')return send(500,{detail:'Não foi possível registrar a devolução'});
     reason=data.reason;state=data.status;await new Promise(resolve=>setTimeout(resolve,200));return send(200,{status:state});
    }
    if(u.pathname.startsWith('/api/'))return send(200,{});return r.continue();
   });
   await page.goto(base+'/finance',{waitUntil:'domcontentloaded'});
   await page.waitForSelector('select[aria-label="Situação do pagamento"]');
   const click=t=>page.evaluate(t=>{const b=[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===t);if(!b)throw Error('Missing '+t);b.click();},t);
   if(originalPaid)await page.select('select[aria-label="Situação do pagamento"]','paid');
   const label=originalPaid?'Registrar devolução':'Cancelar pagamento';
   await page.waitForFunction(label=>[...document.querySelectorAll('button')].some(b=>b.textContent.trim()===label),{},label);
   if(originalPaid)assert.equal(await page.evaluate(()=>[...document.querySelectorAll('button')].some(b=>b.textContent==='Cancelar pagamento')),false);
   await click(label);await page.waitForSelector('dialog[open]');
   assert.equal(await page.$eval('dialog[aria-labelledby="confirm-payment-title"] button[type="submit"]',b=>b.disabled),true);
   await click('Voltar');assert.equal(posts,0);
   await click(label);await page.waitForSelector('textarea[aria-label="Motivo"]');
   await page.type('textarea[aria-label="Motivo"]','  ');assert.equal(await page.$eval('dialog[aria-labelledby="confirm-payment-title"] button[type="submit"]',b=>b.disabled),true);
   await page.$eval('textarea[aria-label="Motivo"]',e=>{e.value='';e.dispatchEvent(new Event('input',{bubbles:true}));});
   await page.type('textarea[aria-label="Motivo"]','Solicitação do cliente <img src=x onerror=alert(1)>');
   if(originalPaid){assert.equal(await page.$eval('dialog[aria-labelledby="confirm-payment-title"] button[type="submit"]',b=>b.disabled),true);await page.click('dialog[aria-labelledby="confirm-payment-title"] input[type="checkbox"]');}
   assert.equal(await page.$eval('dialog[aria-labelledby="confirm-payment-title"] button[type="submit"]',b=>b.disabled),false);
   await page.evaluate(()=>{const b=document.querySelector('dialog[aria-labelledby="confirm-payment-title"] button[type="submit"]');b.click();b.click();});
   if(scenario==='refund-error'){
    await page.waitForFunction(()=>document.querySelector('dialog[aria-labelledby="confirm-payment-title"] [role="alert"]')?.textContent.includes('Não foi possível'));
    assert.equal(state,'paid');assert.ok(await page.$('dialog[open]'));assert.equal(posts,1);
   }else{
    await page.waitForFunction(()=>document.body.textContent.includes('Nenhum pagamento nesta situação'));
    await page.select('select[aria-label="Situação do pagamento"]',state);
    await page.waitForFunction(()=>document.body.textContent.includes('Ver cancelamento')||document.body.textContent.includes('Ver devolução'));
    await page.click('table details summary');
    assert.match(await page.$eval('table details',e=>e.textContent),/Solicitação do cliente <img/);
    assert.equal(await page.$('table details img'),null);
    assert.equal(posts,1);
    assert.equal(await page.evaluate(()=>[...document.querySelectorAll('button')].some(b=>b.textContent===('Registrar devolução')||b.textContent==='Cancelar pagamento')),false);
    await page.screenshot({path:'/workspace/work/manual-refunds/'+scenario+'-preview.png',fullPage:true});
   }
   await page.close();console.log('Passed manual adjustment browser scenario:',scenario);
  }
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
