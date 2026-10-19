const puppeteer=require('puppeteer-core');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await puppeteer.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
  const page=await browser.newPage();await page.setBypassServiceWorker(true);await page.evaluateOnNewDocument(()=>{delete Navigator.prototype.serviceWorker;});
  const base=process.env.SUBSCRIPTIONS_TEST_BASE_URL||'http://127.0.0.1:3004';const token='a'.repeat(43);let posted=false,destination=null;
  await page.setRequestInterception(true);
  page.on('request',req=>{
   const u=new URL(req.url());
   // The invitation fragment must never appear on an HTTP request URL.
   if(!req.isNavigationRequest()) assert.equal(u.hash,'');
   assert.ok(!(req.headers()['referer']||'').includes(token));
   if(u.pathname==='/api/onboarding/tenant'){
    posted=true;assert.equal(req.headers()['x-onboarding-invite'],token);assert.equal(req.headers()['x-onboarding-token'],undefined);
    const body=JSON.parse(req.postData());assert.equal(body.business_name,'Restaurante Convidado');assert.equal(body.invite,undefined);
    return req.respond({status:201,contentType:'application/json',body:JSON.stringify({tenant_id:3,slug:'restauranteconvidado',business_name:body.business_name,admin_email:body.admin_email,custom_domain:null,subscription_required:true})});
   }
   if(u.pathname==='/login'){destination=u.href;return req.abort();}
   if(u.origin!==new URL(base).origin)return req.abort();
   return req.continue();
  });
  await page.goto(base+'/onboarding#invite='+token,{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>document.body.textContent.includes('Cadastro por convite'));
  assert.equal(await page.evaluate(()=>location.hash),'');
  await page.type('input[placeholder="Nome do restaurante"]','Restaurante Convidado');
  await page.evaluate(()=>[...document.querySelectorAll('button')].find(x=>x.textContent==='Continuar').click());
  await page.waitForSelector('input[placeholder="Nome do administrador"]');
  await page.type('input[placeholder="Nome do administrador"]','Owner');
  await page.type('input[type="email"]','owner@example.com');
  await page.type('input[type="password"]','synthetic-password-123');
  await page.evaluate(()=>document.querySelector('form').requestSubmit());
  const deadline=Date.now()+10000;while(!destination&&Date.now()<deadline)await new Promise(r=>setTimeout(r,50));
  assert.ok(posted);assert.ok(destination);assert.equal(new URL(destination).searchParams.get('redirect'),'/subscriptions');
  console.log('PASS onboarding invite: fragment removed, private header, subscription redirect');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
