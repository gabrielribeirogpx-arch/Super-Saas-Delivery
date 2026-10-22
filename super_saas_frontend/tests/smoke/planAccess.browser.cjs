// Local browser fixtures: never contact a payment provider or real database.
const puppeteer=require('puppeteer-core');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await puppeteer.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 const base=process.env.PLAN_ACCESS_TEST_BASE_URL||'http://127.0.0.1:3010';
 try{
  for(const scenario of ['essential','operation','inactive','legacy','error','mobile']){
   const page=await browser.newPage();await page.setBypassServiceWorker(true);
   await page.evaluateOnNewDocument(()=>{delete Navigator.prototype.serviceWorker;});
   await page.setViewport({width:scenario==='mobile'?430:1365,height:900});
   let reads=0;const errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.setRequestInterception(true);
   page.on('request',async req=>{
    const u=new URL(req.url());const send=(status,data)=>req.respond({status,contentType:'application/json',body:JSON.stringify(data)});
    if(u.pathname==='/api/admin/auth/me')return send(200,{id:1,tenant_id:1,name:'Owner',role:'owner',active:true});
    if(u.pathname==='/api/admin/billing/access')return send(scenario==='error'?503:200,{managed:scenario!=='legacy',active:scenario!=='inactive',features:{inventory:{allowed:scenario==='operation',reason:'feature_disabled',limit:null,usage:null}}});
    if(u.pathname==='/api/inventory/items'){reads++;return send(200,[]);}
    if(u.pathname.includes('manifest'))return send(200,{name:'Fixture',icons:[]});
    if(u.pathname.startsWith('/api/'))return send(200,[]);
    if(!['127.0.0.1','localhost'].includes(u.hostname))return req.abort();
    return req.continue();
   });
   await page.goto(base+'/inventory',{waitUntil:'domcontentloaded',timeout:60000});
   await page.waitForFunction(()=>document.querySelector('main') && !document.body.innerText.includes('Validando sessão...'),{timeout:30000});
   await page.waitForFunction(()=>document.querySelector('main')?.innerText.length>0 && !document.body.innerText.includes('Conferindo acesso ao recurso...'),{timeout:30000});
   const content=await page.$eval('main',el=>el.innerText);
   if(['essential','mobile'].includes(scenario)){
    assert.match(content,/Seu plano não inclui este recurso/);assert.match(content,/Ver planos e assinatura/);assert.equal(reads,0);
   }else if(scenario==='inactive'){
    assert.match(content,/Regularize sua assinatura/);assert.equal(reads,0);
   }else if(scenario==='error'){
    assert.match(content,/Não foi possível conferir seu plano/);assert.equal(reads,0);
   }else{
    assert(reads>0);assert(!content.includes('Seu plano não inclui este recurso'));
   }
   assert.deepEqual(errors,[]);await page.close();console.log('PASS plan access '+scenario);
  }
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
