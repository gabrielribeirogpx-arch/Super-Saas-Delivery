const puppeteer = require('puppeteer-core');
const assert = require('node:assert/strict');
const base = process.env.DRIVER_RECOVERY_TEST_BASE_URL || 'http://127.0.0.1:3027';
const origin = 'https://meuburger.fomizero.com.br';
(async () => {
 const browser = await puppeteer.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 try {
  async function pageFor(resetStatus=200) {
   const page=await browser.newPage(); const posts=[];
   await page.setBypassServiceWorker(true);
   await page.evaluateOnNewDocument(()=>{
    delete Navigator.prototype.serviceWorker;
    // An expired token must not prevent public recovery or leak into its requests.
    localStorage.setItem('driver_token','expired.synthetic.session');
   });
   await page.setRequestInterception(true);
   page.on('request',async req=>{
    const url=new URL(req.url());
    if(url.pathname==='/manifest.webmanifest')return req.respond({status:200,contentType:'application/manifest+json',body:'{}'});
    if(url.pathname.startsWith('/api/')) {
     if(req.method()==='POST')posts.push({path:url.pathname,body:JSON.parse(req.postData()),headers:req.headers()});
     const status=url.pathname.endsWith('/reset-password')?resetStatus:202;
     return req.respond({status,contentType:'application/json',body:JSON.stringify({message:'Se os dados corresponderem, enviaremos um link.'})});
    }
    if(url.origin!==origin)return req.abort();
    try {
     const response=await fetch(base+url.pathname+url.search,{redirect:'manual',headers:req.headers()});
     const headers={}; for(const [key,value] of response.headers)if(!['content-encoding','content-length','transfer-encoding','connection'].includes(key))headers[key]=value;
     return req.respond({status:response.status,headers,body:Buffer.from(await response.arrayBuffer())});
    }catch{return req.abort();}
   });
   return {page,posts};
  }
  {
   const {page,posts}=await pageFor();
   await page.goto(origin+'/driver/login',{waitUntil:'networkidle2'});
   await page.click('a[href="/driver/esqueci-senha"]');
   await page.waitForSelector('input[placeholder="minha-pizzaria"]');
   await page.waitForFunction(()=>document.querySelector('input[placeholder="minha-pizzaria"]')?.value==='meuburger');
   for(const width of [320,390,1366]) {await page.setViewport({width,height:850});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
   await page.type('input[type="email"]','driver@example.com');
   await page.click('button[type="submit"]');await page.waitForSelector('[role="status"]');
   assert.equal(posts.length,1);assert.equal(posts[0].path,'/api/driver/auth/forgot-password');
   assert.deepEqual(posts[0].body,{tenant_slug:'meuburger',email:'driver@example.com'});
   assert.equal(posts[0].headers.authorization,undefined);
   assert.equal(new URL(page.url()).pathname,'/driver/esqueci-senha');
   await page.close();console.log('PASS login link; forgot without session; slug; mobile/desktop; no expired bearer');
  }
  {
   const {page,posts}=await pageFor();
   await page.goto(origin+'/driver/redefinir-senha#token=synthetic-reset-token',{waitUntil:'networkidle2'});
   assert.equal(new URL(page.url()).hash,'');
   for(const width of [320,390,1366]) {await page.setViewport({width,height:850});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
   const inputs=await page.$$('input[type="password"]');await inputs[0].type('new-driver-password');await inputs[1].type('different-password');
   await page.click('button[type="submit"]');await page.waitForSelector('[role="alert"]');assert.equal(posts.length,0);
   await inputs[1].focus();await page.keyboard.down('Control');await page.keyboard.press('A');await page.keyboard.up('Control');await page.keyboard.press('Backspace');await inputs[1].type('new-driver-password');await page.click('button[type="submit"]');
   await page.waitForSelector('a[href="/driver/login"]');assert.equal(posts.length,1);
   assert.equal(posts[0].path,'/api/driver/auth/reset-password');assert.equal(posts[0].body.token,'synthetic-reset-token');
   assert.equal(await page.evaluate(()=>localStorage.getItem('driver_token')),null);
   await page.close();console.log('PASS reset fragment removed; mismatch; correct endpoint; driver login return; session cleared');
  }
  {
   const {page,posts}=await pageFor(400);
   await page.goto(origin+'/driver/redefinir-senha#token=synthetic-expired-token',{waitUntil:'networkidle2'});
   for(const input of await page.$$('input[type="password"]'))await input.type('new-driver-password');
   await page.click('button[type="submit"]');await page.waitForSelector('[role="alert"]');
   assert.equal(posts.length,1);assert.ok(await page.$('a[href="/driver/esqueci-senha"]'));
   await page.goto(origin+'/driver/redefinir-senha',{waitUntil:'networkidle2'});
   await page.waitForSelector('[role="alert"]');assert.equal(await page.$('input[type="password"]'),null);
   await page.close();console.log('PASS expired link guidance and missing fragment state');
  }
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
