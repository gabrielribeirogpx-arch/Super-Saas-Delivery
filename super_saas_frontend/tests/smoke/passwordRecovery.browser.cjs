const puppeteer=require('puppeteer-core');const assert=require('node:assert/strict');
const base=process.env.RECOVERY_TEST_BASE_URL||'http://burger.localhost:3016';
(async()=>{const browser=await puppeteer.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});try{
 for(const scenario of ['forgot','reset','expired','missing']){
  const page=await browser.newPage();await page.setBypassServiceWorker(true);const token='synthetic-private-reset-token';let posts=[];
  await page.setRequestInterception(true);page.on('request',req=>{
   const u=new URL(req.url());assert.ok(!(req.headers().referer||'').includes(token));
   if(u.pathname.startsWith('/api/')){
    if(req.method()==='POST'){posts.push(JSON.parse(req.postData()));return req.respond({status:scenario==='expired'?400:scenario==='forgot'?202:200,contentType:'application/json',body:JSON.stringify({message:'Se os dados corresponderem, enviaremos um link.'})});}
    return req.respond({status:200,contentType:'application/json',body:'{}'});
   }
   if(u.origin!==new URL(base).origin)return req.abort();return req.continue();
  });
  await page.setViewport({width:360,height:850});
  if(scenario==='forgot'){
   await page.goto(base+'/esqueci-senha',{waitUntil:'networkidle0'});assert.equal(await page.$eval('input[placeholder="minha-pizzaria"]',e=>e.value),'burger');
   await page.type('input[type="email"]','owner@example.com');await page.click('button');await page.waitForSelector('[role="status"]');assert.equal(posts.length,1);assert.equal(posts[0].tenant_slug,'burger');
  }else{
   await page.goto(base+'/redefinir-senha'+(scenario==='missing'?'':'#token='+token),{waitUntil:'networkidle0'});
   assert.equal(await page.evaluate(()=>location.hash),'');assert.equal(posts.length,0,'opening a link must never consume it');
   if(scenario==='missing'){assert.match(await page.$eval('[role="alert"]',e=>e.textContent),/link completo/);}
   else{
    const fields=await page.$$('input[type="password"]');await fields[0].type('new-password-123');await fields[1].type('different-password');await page.click('button');await page.waitForSelector('[role="alert"]');assert.equal(posts.length,0);
    await fields[1].click();await page.keyboard.down('Control');await page.keyboard.press('A');await page.keyboard.up('Control');await page.keyboard.press('Backspace');await fields[1].type('new-password-123');assert.equal(await fields[1].evaluate(e=>e.value),'new-password-123');await page.evaluate(()=>document.querySelector('form').requestSubmit());
    if(scenario==='expired'){await page.waitForFunction(()=>document.body.textContent.includes('expirado'));}
    else{await page.waitForSelector('a[href="/login"]');assert.ok(await page.$('[role="status"]'));}
    assert.equal(posts.length,1);assert.equal(posts[0].token,token);assert.equal(posts[0].tenant_slug,'burger');
    assert.ok(!(await page.evaluate(()=>JSON.stringify({...sessionStorage,...localStorage}))).includes(token));
   }
  }
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));console.log('PASS password recovery '+scenario);await page.close();
 }
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
