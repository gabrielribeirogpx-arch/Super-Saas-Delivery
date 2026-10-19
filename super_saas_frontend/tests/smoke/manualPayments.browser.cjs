// Fixture-only browser regression. Does not connect to any bank or live backend.
const puppeteer = require('puppeteer-core');
const assert = require('node:assert/strict');
(async () => {
  const browser = await puppeteer.launch({ executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium', headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const base = process.env.MANUAL_PAYMENTS_TEST_BASE_URL || 'http://127.0.0.1:3000';
  try {
    for (const scenario of ['success', 'conflict', 'forbidden']) {
      const page = await browser.newPage();
      await page.setBypassServiceWorker(true);
      await page.setViewport({width: scenario === 'success' ? 1365 : 430, height: 900});
      let paid = false, posts = 0, listReads = 0, cashReads = 0;
      await page.setRequestInterception(true);
      page.on('request', async req => {
        const u = new URL(req.url());
        const send = (status, data) => req.respond({ status, contentType: 'application/json', body: JSON.stringify(data) });
        if (u.pathname === '/api/admin/auth/me') return send(200, { id:1,tenant_id:1,name:'Operador',role:scenario==='forbidden'?'operator':'owner',active:true });
        if (u.pathname === '/api/finance/manual-payments') {
          listReads++;
          const item = {id:9,order_id:9,order_number:4,method:'cash',amount_cents:2990,status:paid?'paid':'pending',order_status:'DELIVERED',created_at:new Date().toISOString(),paid_at:paid?new Date().toISOString():null,confirmed_by:paid?'Operador':null,can_confirm:!paid};
          return send(200,{items: u.searchParams.get('status') === (paid?'paid':'pending') ? [item] : [],total:u.searchParams.get('status') === (paid?'paid':'pending')?1:0,pending_cents:paid?0:2990,paid_cents:paid?2990:0});
        }
        if (u.pathname === '/api/finance/cash/summary') { cashReads++; return send(200,{opening_balance_cents:0,total_in_cents:paid?2990:0,total_out_cents:0,net_cents:paid?2990:0,by_category:{}}); }
        if (u.pathname === '/api/finance/cash/movements') return send(200,[]);
        if (u.pathname === '/api/orders/9/payments/9/status') {
          posts++; assert.deepEqual(JSON.parse(req.postData()),{status:'paid'});
          if(scenario==='conflict')return send(409,{detail:'Pedido cancelado: recebimento manual bloqueado'});
          paid=true;
          await new Promise(resolve=>setTimeout(resolve,300));
          return send(200,{id:9,status:'paid'});
        }
        if (u.pathname.startsWith('/api/')) return send(200,{});
        return req.continue();
      });
      await page.goto(base+'/finance',{waitUntil:'domcontentloaded'});
      const click = text => page.evaluate(t => {const b=[...document.querySelectorAll('button')].find(x=>x.textContent.trim()===t);if(!b)throw Error('Missing button '+t);b.click();},text);
      if(scenario==='forbidden'){
        await page.waitForFunction(()=>document.body.textContent.includes('Recebimentos disponíveis apenas'));
        assert.equal(listReads,0); assert.equal(posts,0);
      }else{
        await page.waitForFunction(()=>document.body.textContent.includes('Confirmar pagamento'));
        await click('Confirmar pagamento');await page.waitForSelector('dialog[open]');
        assert.match(await page.$eval('dialog',el=>el.textContent),/Dinheiro/);
        await click('Voltar');assert.equal(posts,0);
        await click('Confirmar pagamento');await page.waitForSelector('dialog[open]');
        if(scenario==='success'){
          await page.evaluate(()=>{const b=[...document.querySelectorAll('dialog button')].find(x=>x.textContent==='Sim, recebi o pagamento');b.click();b.click();});
          await page.waitForFunction(()=>document.body.textContent.includes('Recebimento registrado.'));
          await page.waitForFunction(()=>document.body.textContent.includes('Nenhum pagamento nesta situação'));
          await page.select('select[aria-label="Situação do pagamento"]','paid');
          await page.waitForFunction(()=>document.body.textContent.includes('Por Operador'));
          assert.equal(posts,1);assert.ok(cashReads>=2);
          assert.equal(await page.$('dialog[open]'),null);
          await page.screenshot({path:'/workspace/work/manual-finance/finance-preview.png',fullPage:true});
        }else{
          await click('Sim, recebi o pagamento');
          await page.waitForFunction(()=>document.querySelector('dialog [role="alert"]')?.textContent.includes('Pedido cancelado'));
          assert.equal(posts,1);assert.equal(paid,false);
          assert.ok(await page.$('dialog[open]'));
          await click('Voltar');
        }
      }
      await page.close();console.log('Passed manual payment browser scenario:',scenario);
    }
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
