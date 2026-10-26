const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const ts = require('typescript');
const vm = require('node:vm');
const { NextRequest } = require('next/server');

test('customer and PWA proxy preserve API prefix, cookie and tenant; menu keeps public path', async () => {
  const calls = [];
  const context = { exports: {}, Headers, Response, process: { env: { STOREFRONT_BACKEND_URL: 'http://backend:8000' } },
    require: name => name === '@/lib/platformDomains' ? {extractPlatformTenantSlug: () => null} : require(name),
    fetch: async (url, options) => { calls.push({url,options}); return new Response('{}',{status:200}); },
  };
  vm.runInNewContext(ts.transpileModule(fs.readFileSync('app/api/[...path]/route.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,context);
  for(const [path,expected] of [['customer-auth/me','/api/public/customer-auth/me'],['customer-auth/orders','/api/public/customer-auth/orders'],['pwa/manifest','/api/public/pwa/manifest'],['pwa/icon/180','/api/public/pwa/icon/180'],['menu','/public/menu']]) {
    await context.exports.GET(new NextRequest('http://localhost/api/public/'+path+'?tenant=alpha',{headers:{cookie:'customer_session=test'}}),{params:{path:['public',...path.split('/')]}});
    const call = calls.at(-1);
    assert.equal(call.url,'http://backend:8000'+expected+'?tenant=alpha');
    assert.equal(call.options.headers.get('x-tenant-id'),'alpha');
    assert.equal(call.options.headers.get('cookie'),'customer_session=test');
  }
});

test('only unauthenticated sessions redirect to login; server errors remain visible', async () => {
  let status = 401;
  const context = {exports:{},URLSearchParams,
    require: name => name === '@/lib/storefrontApi' ? {resolveStorefrontTenant:()=> 'alpha',storefrontFetch:async()=>new Response(JSON.stringify({detail:'Servidor indisponível'}),{status})} : {clearCustomerTrackingData:()=>{}},
  };
  vm.runInNewContext(ts.transpileModule(fs.readFileSync('lib/customerAuth.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,context);
  assert.equal(await context.exports.customerMe(),null);
  for(status of [404,500]) await assert.rejects(()=>context.exports.customerMe(),/Servidor indisponível/);
});
