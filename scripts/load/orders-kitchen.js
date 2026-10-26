import http from 'k6/http';
import { check, sleep } from 'k6';
import exec from 'k6/execution';
import { Rate, Counter } from 'k6/metrics';

// Deliberately fixed to the staging backend verified by the operator.
const BASE = 'https://super-saas-delivery-production.up.railway.app';
const sustained = __ENV.LOADTEST_SUSTAINED === '1';
const total = sustained ? 600 : Number(__ENV.LOADTEST_ORDERS || 10);
const vus = Number(__ENV.LOADTEST_VUS || 2);
if (!Number.isInteger(total) || total < 1 || total > (sustained ? 600 : 100) ||
    !Number.isInteger(vus) || vus < 1 || vus > 30 || vus > total) {
  throw new Error('Use 1..100 pedidos e 1..30 fluxos, sem exceder o total de pedidos.');
}
const failures = new Rate('etapas_invalidas');
const completed = new Counter('pedidos_prontos');
const replays = new Counter('repeticoes_sem_duplicacao');
const excessArrivals = new Counter('chegadas_alem_do_limite');
export const options = {
  setupTimeout: '5m',
  teardownTimeout: '3m',
  scenarios: { pedidos: sustained
    ? { executor: 'constant-arrival-rate', rate: 1, timeUnit: '1s', duration: '10m',
        preAllocatedVUs: 10, maxVUs: 30, gracefulStop: '2m' }
    : { executor: 'shared-iterations', vus, iterations: total, maxDuration: '10m' } },
  // Avoid tokens, arbitrary URLs and credentials in exported metric labels.
  systemTags: ['status', 'method', 'name', 'scenario', 'expected_response'],
  thresholds: {
    etapas_invalidas: [{ threshold: 'rate==0', abortOnFail: true, delayAbortEval: '5s' }],
    'http_req_duration{phase:load}': ['p(95)<2000'],
    // Export operation-level percentiles without changing traffic or credentials.
    ...Object.fromEntries(['cardapio', 'criar_pedido', 'repetir_pedido', 'historico',
      'iniciar_preparo', 'marcar_pronto'].map(name =>
      [`http_req_duration{phase:load,name:${name}}`, ['p(95)<2000']])),
    pedidos_prontos: [`count==${total}`],
    repeticoes_sem_duplicacao: [`count==${total}`],
    ...(sustained ? { dropped_iterations: ['count==0'] } : {}),
    ...Object.fromEntries(sustained ? Array.from({length: 10}, (_, minute) =>
      [`http_req_duration{phase:load,minute:${minute}}`, ['p(95)<2000']]) : []),
  },
};

function abort(message) { exec.test.abort(message); throw new Error(message); }
function ensure(ok, label) {
  check(ok, { [label]: value => value });
  failures.add(!ok);
  if (!ok) abort(label + ' falhou; lote interrompido. Veja status HTTP no relatorio.');
}
function send(store, method, path, payload, name, phase, admin = false, key = null) {
  // Prevent a previous store's admin cookie leaking into public/other-store calls.
  http.cookieJar().clear(BASE);
  const headers = { 'Content-Type': 'application/json', 'X-Tenant-Slug': store.slug };
  if (key) headers['Idempotency-Key'] = key;
  const r = http.request(method, BASE + path, payload === null ? null : JSON.stringify(payload), {
    headers, cookies: admin ? { admin_session: store.cookie } : {},
    timeout: '15s', redirects: 0, tags: { name, phase, loja: store.slug, minute: phase === 'load'
      ? String(Math.min(10, Math.max(0, Math.floor((Date.now() - exec.scenario.startTime) / 60000))))
      : 'other' },
  });
  let body;
  try { body = r.json(); } catch (_) { body = null; }
  ensure(r.status >= 200 && r.status < 300 && body !== null, name + ' HTTP ' + r.status);
  return { body, response: r };
}
function history(store, marker, phase, page = 1) {
  return send(store, 'GET', `/api/orders/${store.id}/search?page=${page}&page_size=100&customer=${encodeURIComponent(marker)}`,
    null, 'historico', phase, true).body;
}
function findOwnOrder(store, marker, token, phase) {
  const h = history(store, marker, phase);
  ensure(h.total === 1 && Array.isArray(h.items) && h.items.length === 1, 'pedido unico no historico');
  const order = h.items[0];
  ensure(order.tenant_id === store.id && order.customer_name === marker &&
    order.tracking_token === token && Number.isInteger(order.id), 'identidade do pedido');
  return order;
}

export function setup() {
  if (__ENV.LOADTEST_ISOLATED !== 'SIM') abort('Confirme loja de staging e integracoes externas desativadas.');
  let credentials;
  try { credentials = JSON.parse(__ENV.LOADTEST_STORES || '[]'); }
  catch (_) { abort('Configuracao das lojas invalida.'); }
  if (!Array.isArray(credentials) || !credentials.length || credentials.length > 30) abort('Informe 1..30 lojas de teste.');
  if (sustained && credentials.length < 5) abort('Modo sustentado exige pelo menos 5 lojas de teste.');
  const run = `LT-${Date.now()}-${Math.random().toString(16).slice(2, 10).padEnd(8, '0')}`;
  const stores = [];
  for (const entry of credentials) {
    if (!/^[a-z0-9-]+$/.test(entry.slug || '') || !entry.email || !entry.password) abort('Credenciais incompletas.');
    if (stores.some(s => s.slug === entry.slug)) abort('Loja repetida na configuracao.');
    const store = { slug: entry.slug };
    const menu = send(store, 'GET', `/public/menu?slug=${encodeURIComponent(store.slug)}`, null, 'cardapio', 'setup').body;
    ensure(menu.slug === store.slug && menu.tenant && menu.tenant.id === menu.tenant_id, 'loja do cardapio');
    store.id = menu.tenant_id;
    const products = (menu.items_without_category || []).concat((menu.categories || []).flatMap(c => c.items || []));
    const product = products.find(p => (!entry.item_id || p.id === Number(entry.item_id)) &&
      !(p.modifier_groups || []).some(g => g.required || g.min_selection > 0));
    ensure(!!product, 'produto sem adicionais obrigatorios disponivel');
    store.item = product.id;
    const policy = send(store, 'GET', '/public/checkout-policy', null, 'politica', 'setup').body;
    ensure((policy.methods || []).some(m => m.id === 'money' && m.available), 'pagamento em dinheiro disponivel');
    const login = send(store, 'POST', '/api/admin/auth/login',
      { email: entry.email, password: entry.password, tenant_slug: store.slug }, 'login', 'setup');
    ensure(login.body.active && login.body.tenant_id === store.id, 'usuario da loja correta');
    const cookies = login.response.cookies.admin_session || [];
    ensure(cookies.length > 0 && !!cookies[0].value, 'sessao administrativa');
    store.cookie = cookies[0].value;
    const me = send(store, 'GET', '/api/admin/auth/me', null, 'sessao', 'setup', true).body;
    ensure(me.tenant_id === store.id, 'sessao vinculada a loja');
    ensure(history(store, run, 'setup').total === 0, 'identificador de lote novo');
    stores.push(store);
  }
  console.log(`Lote ${run}: ate ${total} pedidos em ${stores.length} loja(s). ` +
    (sustained ? '1 novo pedido/s no total durante 10 minutos; ate 30 VUs.' : `${vus} fluxos.`));
  return { run, stores };
}

export default function (data) {
  const index = exec.scenario.iterationInTest;
  // A boundary arrival may be scheduled at duration end. Do not create another
  // order or abort the test: existing iterations must finish during gracefulStop.
  if (index >= total) {
    excessArrivals.add(1);
    return;
  }
  const store = data.stores[index % data.stores.length];
  // Trailing separator prevents a search for iteration 1 matching iteration 10.
  const marker = `${data.run}-${index}-END`;
  const key = `${data.run}-order-${index}`;
  send(store, 'GET', `/public/menu?slug=${encodeURIComponent(store.slug)}`, null, 'cardapio', 'load');
  const payload = {
    store_id: store.id, customer_name: marker, customer_phone: '', customer_email: '',
    order_type: 'pickup', delivery_type: 'retirada', payment_method: 'money',
    notes: `TESTE DE CARGA ${data.run} - NAO PRODUZIR`,
    items: [{ item_id: store.item, quantity: 1 }],
  };
  const created = send(store, 'POST', '/public/orders', payload, 'criar_pedido', 'load', false, key).body;
  ensure(typeof created.tracking_token === 'string' && !!created.tracking_token &&
    Number.isInteger(created.order_number), 'pedido criado');
  const replay = send(store, 'POST', '/public/orders', payload, 'repetir_pedido', 'load', false, key).body;
  ensure(replay.tracking_token === created.tracking_token && replay.order_number === created.order_number &&
    replay.total === created.total, 'resposta idempotente');
  const order = findOwnOrder(store, marker, created.tracking_token, 'load');
  replays.add(1);
  for (const status of ['EM_PREPARO', 'PRONTO']) {
    sleep(1);
    const changed = send(store, 'PATCH', `/api/orders/${order.id}/status`, { status },
      status === 'PRONTO' ? 'marcar_pronto' : 'iniciar_preparo', 'load', true).body;
    ensure(changed.ok === true, 'atualizacao aceita');
    const persisted = findOwnOrder(store, marker, created.tracking_token, 'load');
    ensure(persisted.status === status, 'status persistido ' + status);
  }
  completed.add(1);
}

export function teardown(data) {
  if (!data || !data.stores) return;
  for (let i = 0; i < data.stores.length; i++) {
    const store = data.stores[i];
    const expected = Math.floor(total / data.stores.length) + (i < total % data.stores.length ? 1 : 0);
    const h = history(store, data.run, 'teardown');
    ensure(h.total === expected && Array.isArray(h.items), 'quantidade final ' + store.slug);
    const rows = h.items.slice();
    for (let page = 2; page <= Math.ceil(expected / 100); page++) {
      const next = history(store, data.run, 'teardown', page);
      ensure(next.total === expected && Array.isArray(next.items), 'pagina final ' + store.slug);
      rows.push(...next.items);
    }
    ensure(rows.length === expected && rows.every(o => o.tenant_id === store.id && o.status === 'PRONTO' &&
      o.customer_name.startsWith(data.run + '-')) && new Set(rows.map(o => o.id)).size === expected &&
      new Set(rows.map(o => o.customer_name)).size === expected && new Set(rows.map(o => o.tracking_token)).size === expected,
      'reconciliacao final ' + store.slug);
    console.log(`Loja ${store.slug}: ${rows.length}/${expected} pedidos encontrados, todos PRONTO.`);
  }
}
