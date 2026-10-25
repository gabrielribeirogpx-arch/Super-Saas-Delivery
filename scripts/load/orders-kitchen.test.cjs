const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const test = require('node:test');
const source = fs.readFileSync(__dirname + '/orders-kitchen.js', 'utf8')
  .replace(/^import .*;\n/gm, '')
  .replace('export const options', 'const options')
  .replace('export default function (data)', 'function iteration(data)')
  .replace(/export function /g, 'function ')
  + '\nthis.api = {setup, iteration, teardown, options};';
function harness({corruptReplay=false, wrongTenant=false, timeout=false, invalidEnv=false, sustained=false, storeCount=sustained?5:2}={}) {
  const orders = [], calls = [], receipts = new Map();
  const metrics = {};
  class Metric { constructor(n) { this.n=n; metrics[n]=[]; } add(v) { metrics[this.n].push(v); } }
  const execution = {scenario:{iterationInTest:0,startTime:Date.now()},test:{abort(m){throw new Error(m);}}};
  const context = {
    __ENV: {LOADTEST_ISOLATED: invalidEnv ? '' : 'SIM', LOADTEST_ORDERS:'4', LOADTEST_VUS:'2',
      LOADTEST_SUSTAINED:sustained?'1':'0',
      LOADTEST_STORES:JSON.stringify(Array.from({length:storeCount},(_,i)=>({slug:`test-${i+1}`,email:`user${i}@test.local`,password:'secret'})))},
    check:(v, checks)=>Object.values(checks).every(f=>f(v)), sleep:()=>{}, exec:execution,
    Rate:Metric, Counter:Metric, console:{log:()=>{}},
    http:{cookieJar:()=>({clear(){}}),request(method,url,raw,params){
      const u=new URL(url); const slug=params.headers['X-Tenant-Slug']; const id=Number(slug.split('-')[1]);
      const body=raw ? JSON.parse(raw):null; calls.push({method,path:u.pathname,body,params});
      assert.equal(u.origin,'https://super-saas-delivery-production.up.railway.app');
      if (u.pathname.startsWith('/api/orders/') || u.pathname.endsWith('/me')) {
        assert.equal(params.cookies.admin_session,`cookie-${id}`);
      } else assert.deepEqual(Object.keys(params.cookies),[]);
      let result, cookies={};
      if(u.pathname==='/public/menu') result={slug,tenant:{id},tenant_id:id,categories:[{items:[{id:100+id,modifier_groups:[]}]}]};
      else if(u.pathname==='/public/checkout-policy') result={methods:[{id:'money',available:true}]};
      else if(u.pathname.endsWith('/login')) {result={active:true,tenant_id:id};cookies={admin_session:[{value:`cookie-${id}`}]};}
      else if(u.pathname.endsWith('/me')) result={tenant_id:id};
      else if(u.pathname==='/public/orders') {
        assert.equal(body.customer_phone,'');assert.equal(body.order_type,'pickup');assert.equal(body.payment_method,'money');
        const key=params.headers['Idempotency-Key'];assert.ok(key.length>=32 && key.length<=128);
        if(timeout) return {status:0,json(){throw new Error('timeout');}};
        if(receipts.has(key)) result={...receipts.get(key),...(corruptReplay?{tracking_token:'different'}:{})};
        else {
          const order={id:orders.length+1,tenant_id:id,customer_name:body.customer_name,tracking_token:`token-${orders.length+1}`,status:'pending'};
          orders.push(order); result={tracking_token:order.tracking_token,order_number:order.id,total:2990};receipts.set(key,result);
        }
      } else if(u.pathname.endsWith('/search')) {
        const rows=orders.filter(o=>o.tenant_id===id && o.customer_name.includes(u.searchParams.get('customer')));
        const page=Number(u.searchParams.get('page')||1);
        result={total:rows.length,items:rows.slice((page-1)*100,page*100).map(o=>({...o,tenant_id:wrongTenant?999:o.tenant_id}))};
      } else if(u.pathname.endsWith('/status')) {
        const oid=Number(u.pathname.split('/')[3]); const order=orders.find(o=>o.id===oid);
        assert.equal(order.tenant_id,id);order.status=body.status;result={ok:true,status:body.status};
      } else throw new Error('Unexpected route '+u.pathname);
      return {status:200,cookies,json:()=>result};
    }},
  };
  vm.createContext(context);vm.runInContext(source,context);
  return {api:context.api,execution,orders,calls,metrics};
}
test('multiple stores: bounded creates, replay identity, cookie isolation and persisted statuses',()=>{
  const h=harness();const data=h.api.setup();
  for(let i=0;i<4;i++){h.execution.scenario.iterationInTest=i;h.api.iteration(data);}
  h.api.teardown(data);
  assert.equal(h.orders.length,4);assert.ok(h.orders.every(o=>o.status==='PRONTO'));
  assert.equal(h.metrics.pedidos_prontos.length,4);assert.equal(h.metrics.repeticoes_sem_duplicacao.length,4);
  assert.equal(h.calls.filter(c=>c.path==='/public/orders').length,8);
});
test('refuses writes without staging isolation acknowledgement',()=>{
 const h=harness({invalidEnv:true});assert.throws(()=>h.api.setup());assert.equal(h.calls.length,0);
});
for(const config of [{corruptReplay:true},{wrongTenant:true},{timeout:true}]) {
 test('stops before status writes: '+JSON.stringify(config),()=>{
  const h=harness(config);const data=h.api.setup();assert.throws(()=>h.api.iteration(data));
  assert.equal(h.calls.filter(c=>c.method==='PATCH').length,0);
 });
}
test('final reconciliation rejects a duplicate',()=>{
 const h=harness();const data=h.api.setup();
 for(let i=0;i<4;i++){h.execution.scenario.iterationInTest=i;h.api.iteration(data);}
 h.orders.push({...h.orders[0],id:999});assert.throws(()=>h.api.teardown(data));
});

test('sustained schedules 600 arrivals over ten minutes and reconciles 120 orders per store across pages',()=>{
 const h=harness({sustained:true}); const scenario=h.api.options.scenarios.pedidos;
 assert.equal(scenario.executor,'constant-arrival-rate');
 assert.equal(scenario.rate,1);assert.equal(scenario.timeUnit,'1s');assert.equal(scenario.duration,'10m');
 assert.equal(scenario.maxVUs,20);assert.equal(scenario.gracefulStop,'2m');
 assert.equal(h.api.options.thresholds.dropped_iterations[0],'count==0');
 assert.equal(h.api.options.thresholds.pedidos_prontos[0],'count==600');
 for(let m=0;m<10;m++) assert.ok(h.api.options.thresholds[`http_req_duration{phase:load,minute:${m}}`]);
 const data=h.api.setup();
 for(let i=0;i<600;i++){h.execution.scenario.iterationInTest=i;h.api.iteration(data);}
 h.api.teardown(data);
 assert.equal(h.orders.length,600);assert.equal(h.metrics.pedidos_prontos.length,600);
 for(let id=1;id<=5;id++) assert.equal(h.orders.filter(o=>o.tenant_id===id).length,120);
 const before = h.calls.length;
 h.execution.scenario.iterationInTest=600;assert.doesNotThrow(()=>h.api.iteration(data));
 assert.equal(h.calls.length,before);
 assert.equal(h.metrics.chegadas_alem_do_limite.length,1);
 assert.equal(h.orders.length,600);
});
test('sustained refuses fewer than five stores before sending any requests',()=>{
 const h=harness({sustained:true,storeCount:1});assert.throws(()=>h.api.setup());assert.equal(h.calls.length,0);
});

test('boundary arrival does not abort remaining work or weaken completion thresholds',()=>{
 const h=harness({sustained:true});const data=h.api.setup();
 for(let i=0;i<599;i++){h.execution.scenario.iterationInTest=i;h.api.iteration(data);}
 const before=h.calls.length;
 h.execution.scenario.iterationInTest=600;h.api.iteration(data);
 assert.equal(h.calls.length,before);
 assert.equal(h.metrics.pedidos_prontos.length,599);
 assert.equal(h.api.options.thresholds.pedidos_prontos[0],'count==600');
 h.execution.scenario.iterationInTest=599;h.api.iteration(data);
 assert.equal(h.metrics.pedidos_prontos.length,600);
 assert.doesNotThrow(()=>h.api.teardown(data));
 assert.equal(h.orders.length,600);
});
