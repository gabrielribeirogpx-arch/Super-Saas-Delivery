const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs'); const path = require('node:path'); const Module = require('node:module'); const ts = require('typescript');
const oldLoad = Module._load, oldTs = require.extensions['.ts'];
Module._load = function(request, parent, main) { if(request==='./storefrontApi.ts') return {storefrontFetch:()=>{throw Error('No network in policy unit tests');}}; return oldLoad.call(this,request,parent,main); };
require.extensions['.ts'] = (module,file)=>module._compile(ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,file);
const {parseCheckoutPolicy,canUseCheckoutMethod}=require('../lib/checkoutPolicy.ts');
Module._load=oldLoad; require.extensions['.ts']=oldTs;
test('no fallback methods on missing or malformed server policy',()=>{
 for(const value of [null,{}, {methods:'pix'}, {methods:[{id:'pix',label:'Pix',available:'true'}]}, {methods:[{id:'invented',label:'Pay',available:true}]}]) assert.throws(()=>parseCheckoutPolicy(value));
 assert.equal(canUseCheckoutMethod(null,'pix'),false);
});
test('free native-only policy cannot accidentally select manual or unavailable methods',()=>{
 const policy=parseCheckoutPolicy({methods:[{id:'native_pix',label:'Pix online',available:false},{id:'native_card',label:'Cartão online',available:false}],message:'Indisponível'});
 for(const id of ['pix','money','card','native_pix','native_card']) assert.equal(canUseCheckoutMethod(policy,id),false);
});
test('paid manual methods follow server availability, not client defaults',()=>{
 const policy=parseCheckoutPolicy({methods:[{id:'money',label:'Dinheiro',available:true},{id:'native_pix',label:'Pix online',available:false}],message:null});
 assert.equal(canUseCheckoutMethod(policy,'money'),true); assert.equal(canUseCheckoutMethod(policy,'pix'),false); assert.equal(canUseCheckoutMethod(policy,'native_pix'),false);
});
test('duplicate method ids are rejected',()=>{
 const method={id:'pix',label:'Pix',available:true}; assert.throws(()=>parseCheckoutPolicy({methods:[method,method]}));
});
