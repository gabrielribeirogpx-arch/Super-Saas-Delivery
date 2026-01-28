from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["admin"])


@router.get("/admin/{tenant_id}/menu", response_class=HTMLResponse)
def admin_menu(tenant_id: int):
    html = f"""
<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Painel do Dono • Cardápio (Tenant {tenant_id})</title>
  <style>
    :root {{
      --bg: #0b0f14;
      --card: #121826;
      --muted: #91a4b7;
      --text: #e7eef6;
      --border: rgba(255,255,255,0.08);
      --shadow: 0 10px 30px rgba(0,0,0,.35);
      --radius: 14px;
      --accent: #ffb86b;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial;
      background: radial-gradient(1000px 700px at 10% 0%, #142136 0%, var(--bg) 60%);
      color: var(--text);
    }}
    header {{
      padding: 18px 22px;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
    }}
    .brand {{ display: flex; align-items: center; gap: 10px; }}
    .logo {{
      width: 34px; height: 34px;
      border-radius: 10px;
      background: linear-gradient(135deg, #ffb86b, #ff4d6d);
      box-shadow: var(--shadow);
    }}
    .title {{ display: flex; flex-direction: column; line-height: 1.1; }}
    .title b {{ font-size: 16px; }}
    .title span {{ font-size: 12px; color: var(--muted); }}
    .pill {{
      padding: 8px 10px;
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.03);
      border-radius: 999px;
      color: var(--muted);
      font-size: 12px;
    }}
    .btn {{
      cursor: pointer;
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.04);
      color: var(--text);
      padding: 9px 12px;
      border-radius: 10px;
      transition: .15s ease;
    }}
    .btn:hover {{ background: rgba(255,255,255,0.08); }}
    main {{ padding: 18px 18px 26px; }}
    .layout {{ display: grid; grid-template-columns: 260px 1fr; gap: 14px; }}
    .card {{
      background: rgba(255,255,255,0.03);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
    }}
    .section {{ padding: 14px; border-bottom: 1px solid var(--border); }}
    .section:last-child {{ border-bottom: none; }}
    .section h3 {{ margin: 0 0 10px; font-size: 14px; letter-spacing: .3px; }}
    .list {{ display: grid; gap: 8px; }}
    .item {{
      padding: 10px 12px;
      border: 1px solid var(--border);
      border-radius: 10px;
      background: rgba(255,255,255,0.03);
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 10px;
    }}
    .item small {{ color: var(--muted); }}
    .tag {{
      font-size: 11px;
      padding: 4px 8px;
      border-radius: 999px;
      background: rgba(255,184,107,0.18);
      color: var(--accent);
      border: 1px solid rgba(255,184,107,0.3);
    }}
    .grid {{ display: grid; gap: 12px; }}
    .form-grid {{ display: grid; gap: 10px; }}
    label {{ font-size: 12px; color: var(--muted); display: block; margin-bottom: 4px; }}
    input, select, textarea {{
      width: 100%;
      background: rgba(255,255,255,0.04);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 8px 10px;
      border-radius: 8px;
      font-size: 13px;
    }}
    textarea {{ min-height: 80px; resize: vertical; }}
    .actions {{ display: flex; gap: 8px; flex-wrap: wrap; }}
    .muted {{ color: var(--muted); font-size: 12px; }}
    .checkbox-list {{ display: grid; gap: 6px; }}
    .checkbox-list label {{ font-size: 12px; color: var(--text); display: flex; gap: 8px; align-items: center; }}
    .note {{ font-size: 12px; color: var(--muted); margin-top: 6px; }}
    .status {{ font-size: 12px; color: var(--muted); }}
    .item-actions {{ display: flex; gap: 6px; }}
    @media (max-width: 980px) {{
      .layout {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
<header>
  <div class="brand">
    <div class="logo"></div>
    <div class="title">
      <b>Painel do Dono • Cardápio</b>
      <span>Tenant {tenant_id} • MVP simples</span>
    </div>
  </div>
  <div class="actions">
    <span class="pill" id="status">Carregando…</span>
    <a class="btn" href="/admin/{tenant_id}/dashboard">Dashboard</a>
    <a class="btn" href="/admin/{tenant_id}/modifiers">Gerenciar adicionais</a>
  </div>
</header>
<main>
  <div class="layout">
    <div class="card">
      <div class="section">
        <h3>Categorias</h3>
        <div class="list" id="categories"></div>
      </div>
    </div>
    <div class="grid">
      <div class="card">
        <div class="section" style="display:flex; align-items:center; justify-content:space-between; gap:12px;">
          <div>
            <h3>Itens</h3>
            <div class="muted" id="items-count">0 itens</div>
          </div>
          <button class="btn" onclick="startCreate()">Criar item</button>
        </div>
        <div class="section">
          <div class="list" id="items"></div>
        </div>
      </div>
      <div class="card">
        <div class="section">
          <h3 id="form-title">Criar item</h3>
          <form class="form-grid" onsubmit="event.preventDefault(); saveItem();">
            <div>
              <label for="name">Nome</label>
              <input id="name" required />
            </div>
            <div>
              <label for="description">Descrição (não salva no backend)</label>
              <textarea id="description" placeholder="Opcional"></textarea>
              <div class="note">Campo informativo apenas no MVP.</div>
            </div>
            <div>
              <label for="price">Preço (centavos)</label>
              <input id="price" type="number" min="0" required />
            </div>
            <div>
              <label for="category">Categoria</label>
              <select id="category"></select>
            </div>
            <div>
              <label>Grupos de adicionais</label>
              <div class="checkbox-list" id="groups"></div>
              <div class="note">Marque os grupos que este item deve oferecer.</div>
            </div>
            <div class="actions">
              <button class="btn" type="submit">Salvar</button>
              <button class="btn" type="button" onclick="clearForm()">Limpar</button>
            </div>
          </form>
          <div class="status" id="form-status"></div>
        </div>
      </div>
    </div>
  </div>
</main>
<script>
  const TENANT_ID = {tenant_id};
  const state = {{
    categories: [],
    items: [],
    groups: [],
    selectedCategoryId: null,
    editingItem: null,
  }};

  const statusEl = document.getElementById('status');
  const itemsCountEl = document.getElementById('items-count');
  const categoriesEl = document.getElementById('categories');
  const itemsEl = document.getElementById('items');
  const groupsEl = document.getElementById('groups');
  const formTitleEl = document.getElementById('form-title');
  const formStatusEl = document.getElementById('form-status');

  const nameInput = document.getElementById('name');
  const descInput = document.getElementById('description');
  const priceInput = document.getElementById('price');
  const categorySelect = document.getElementById('category');

  async function fetchJson(url, options = {{}}) {{
    const response = await fetch(url, {{
      headers: {{ 'Content-Type': 'application/json' }},
      ...options,
    }});
    if (!response.ok) {{
      let detail = 'Erro ao comunicar com a API.';
      try {{
        const data = await response.json();
        if (data && data.detail) detail = data.detail;
      }} catch (err) {{
        // ignore
      }}
      throw new Error(detail);
    }}
    return response.json();
  }}

  function setStatus(message) {{
    statusEl.textContent = message;
  }}

  function setFormStatus(message) {{
    formStatusEl.textContent = message;
  }}

  function renderCategories() {{
    categoriesEl.innerHTML = '';
    const allBtn = document.createElement('button');
    allBtn.className = 'btn';
    allBtn.textContent = 'Todas';
    allBtn.onclick = () => selectCategory(null);
    categoriesEl.appendChild(allBtn);

    state.categories.forEach((cat) => {{
      const btn = document.createElement('button');
      btn.className = 'btn';
      btn.textContent = cat.name;
      btn.onclick = () => selectCategory(cat.id);
      categoriesEl.appendChild(btn);
    }});

    categorySelect.innerHTML = '<option value="">Sem categoria</option>';
    state.categories.forEach((cat) => {{
      const option = document.createElement('option');
      option.value = cat.id;
      option.textContent = cat.name;
      categorySelect.appendChild(option);
    }});
  }}

  function formatPrice(value) {{
    const cents = Number(value || 0);
    return (cents / 100).toLocaleString('pt-BR', {{ style: 'currency', currency: 'BRL' }});
  }}

  function renderItems() {{
    itemsEl.innerHTML = '';
    itemsCountEl.textContent = `${{state.items.length}} itens`;
    if (!state.items.length) {{
      itemsEl.innerHTML = '<div class="muted">Nenhum item nesta categoria.</div>';
      return;
    }}
    state.items.forEach((item) => {{
      const row = document.createElement('div');
      row.className = 'item';
      row.innerHTML = `
        <div>
          <div><strong>${{item.name}}</strong></div>
          <small>${{formatPrice(item.price_cents)}} • Categoria ${{item.category_id ?? '—'}}</small>
        </div>
        <div class="item-actions">
          <span class="tag">ID ${{item.id}}</span>
          <button class="btn" onclick="editItem(${{item.id}})">Editar</button>
        </div>
      `;
      itemsEl.appendChild(row);
    }});
  }}

  function renderGroups(selectedIds = []) {{
    groupsEl.innerHTML = '';
    if (!state.groups.length) {{
      groupsEl.innerHTML = '<div class="muted">Nenhum grupo cadastrado.</div>';
      return;
    }}
    state.groups.forEach((group) => {{
      const label = document.createElement('label');
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.value = group.id;
      checkbox.checked = selectedIds.includes(group.id);
      label.appendChild(checkbox);
      const span = document.createElement('span');
      span.textContent = group.name;
      label.appendChild(span);
      groupsEl.appendChild(label);
    }});
  }}

  function selectCategory(categoryId) {{
    state.selectedCategoryId = categoryId;
    loadItems();
  }}

  async function loadCategories() {{
    state.categories = await fetchJson(`/api/menu/categories?tenant_id=${{TENANT_ID}}`);
    renderCategories();
  }}

  async function loadItems() {{
    setStatus('Carregando itens…');
    let url = `/api/menu?tenant_id=${{TENANT_ID}}`;
    if (state.selectedCategoryId !== null && state.selectedCategoryId !== undefined) {{
      url += `&category_id=${{state.selectedCategoryId}}`;
    }}
    state.items = await fetchJson(url);
    renderItems();
    setStatus('Pronto');
  }}

  async function loadGroups() {{
    state.groups = await fetchJson(`/api/modifiers/groups/${{TENANT_ID}}`);
    renderGroups();
  }}

  async function loadItemGroups(itemId) {{
    if (!itemId) {{
      renderGroups();
      return;
    }}
    const response = await fetch(`/api/modifiers/menu/${{TENANT_ID}}/${{itemId}}/groups`);
    if (!response.ok) {{
      renderGroups();
      return;
    }}
    const data = await response.json();
    const ids = Array.isArray(data.group_ids) ? data.group_ids : [];
    renderGroups(ids);
  }}

  function startCreate() {{
    state.editingItem = null;
    formTitleEl.textContent = 'Criar item';
    nameInput.value = '';
    descInput.value = '';
    priceInput.value = '';
    categorySelect.value = '';
    renderGroups();
    setFormStatus('');
  }}

  function editItem(itemId) {{
    const item = state.items.find((i) => i.id === itemId);
    if (!item) return;
    state.editingItem = item;
    formTitleEl.textContent = `Editar item #${{item.id}}`;
    nameInput.value = item.name;
    descInput.value = '';
    priceInput.value = item.price_cents;
    categorySelect.value = item.category_id ?? '';
    loadItemGroups(item.id);
    setFormStatus('');
    window.scrollTo({{ top: document.body.scrollHeight, behavior: 'smooth' }});
  }}

  function clearForm() {{
    startCreate();
  }}

  function getSelectedGroupIds() {{
    return Array.from(groupsEl.querySelectorAll('input[type="checkbox"]'))
      .filter((checkbox) => checkbox.checked)
      .map((checkbox) => Number(checkbox.value));
  }}

  async function saveItem() {{
    setFormStatus('Salvando…');
    const payload = {{
      name: nameInput.value.trim(),
      price_cents: Number(priceInput.value || 0),
      category_id: categorySelect.value ? Number(categorySelect.value) : null,
    }};

    try {{
      let item = null;
      if (state.editingItem) {{
        item = await fetchJson(`/api/menu/${{TENANT_ID}}/${{state.editingItem.id}}`, {{
          method: 'PUT',
          body: JSON.stringify(payload),
        }});
      }} else {{
        item = await fetchJson(`/api/menu/${{TENANT_ID}}`, {{
          method: 'POST',
          body: JSON.stringify(payload),
        }});
      }}

      const groupIds = getSelectedGroupIds();
      await fetchJson(`/api/modifiers/menu/${{TENANT_ID}}/${{item.id}}/groups`, {{
        method: 'POST',
        body: JSON.stringify({{ group_ids: groupIds }}),
      }});

      setFormStatus('Item salvo e grupos associados.');
      await loadItems();
      state.editingItem = item;
    }} catch (err) {{
      setFormStatus(err.message || 'Erro ao salvar.');
    }}
  }}

  async function init() {{
    try {{
      setStatus('Carregando dados…');
      await Promise.all([loadCategories(), loadGroups()]);
      await loadItems();
      startCreate();
    }} catch (err) {{
      setStatus('Erro ao carregar.');
      setFormStatus(err.message || 'Erro ao iniciar.');
    }}
  }}

  init();
</script>
</body>
</html>
"""
    return HTMLResponse(html)


@router.get("/admin/{tenant_id}/dashboard", response_class=HTMLResponse)
def admin_dashboard(tenant_id: int):
    html = f"""
<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Painel do Dono • Dashboard (Tenant {tenant_id})</title>
  <style>
    :root {{
      --bg: #0b0f14;
      --card: #121826;
      --muted: #91a4b7;
      --text: #e7eef6;
      --border: rgba(255,255,255,0.08);
      --shadow: 0 10px 30px rgba(0,0,0,.35);
      --radius: 16px;
      --accent: #ff8a4c;
      --accent-2: #63e6be;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial;
      background: radial-gradient(1200px 700px at 10% 0%, #18253a 0%, var(--bg) 60%);
      color: var(--text);
    }}
    header {{
      padding: 18px 22px;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      flex-wrap: wrap;
    }}
    .brand {{ display: flex; align-items: center; gap: 12px; }}
    .logo {{
      width: 36px; height: 36px;
      border-radius: 12px;
      background: linear-gradient(135deg, #ffb86b, #ff4d6d);
      box-shadow: var(--shadow);
    }}
    .title {{ display: flex; flex-direction: column; line-height: 1.1; }}
    .title b {{ font-size: 18px; }}
    .title span {{ font-size: 12px; color: var(--muted); }}
    .pill {{
      padding: 8px 12px;
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.03);
      border-radius: 999px;
      color: var(--muted);
      font-size: 12px;
    }}
    .btn {{
      cursor: pointer;
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.04);
      color: var(--text);
      padding: 9px 12px;
      border-radius: 10px;
      transition: .15s ease;
      font-size: 12px;
    }}
    .btn:hover {{ background: rgba(255,255,255,0.08); }}
    .btn.active {{
      border-color: rgba(255,138,76,0.6);
      color: var(--accent);
      background: rgba(255,138,76,0.12);
    }}
    main {{ padding: 18px 20px 28px; display: grid; gap: 16px; }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(4, minmax(180px, 1fr));
      gap: 12px;
    }}
    .card {{
      background: rgba(255,255,255,0.03);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      padding: 14px;
      display: grid;
      gap: 6px;
    }}
    .card h3 {{
      margin: 0;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: .6px;
      color: var(--muted);
    }}
    .card strong {{
      font-size: 20px;
      letter-spacing: .3px;
    }}
    .muted {{ color: var(--muted); font-size: 12px; }}
    .grid {{
      display: grid;
      grid-template-columns: 2fr 1fr;
      gap: 14px;
    }}
    .chart-card {{
      background: rgba(255,255,255,0.03);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 14px;
    }}
    .chart-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 12px;
    }}
    canvas {{ width: 100%; height: 220px; }}
    .list {{ display: grid; gap: 10px; }}
    .list-item {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 10px;
      padding: 10px 12px;
      border-radius: 10px;
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.03);
      font-size: 13px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    th, td {{
      padding: 8px 10px;
      text-align: left;
      border-bottom: 1px solid var(--border);
    }}
    th {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .4px; }}
    .section-card {{
      background: rgba(255,255,255,0.03);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 14px;
    }}
    .filters {{
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .filters input {{
      background: rgba(255,255,255,0.04);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 8px 10px;
      border-radius: 8px;
      font-size: 12px;
    }}
    .actions {{
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }}
    @media (max-width: 1100px) {{
      .cards {{ grid-template-columns: repeat(2, minmax(180px, 1fr)); }}
      .grid {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 720px) {{
      header {{ align-items: flex-start; }}
      .cards {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
<header>
  <div class="brand">
    <div class="logo"></div>
    <div class="title">
      <b>Dashboard</b>
      <span>Tenant {tenant_id} • visão financeira</span>
    </div>
  </div>
  <div class="actions">
    <span class="pill" id="status">Carregando…</span>
    <div class="filters">
      <button class="btn active" data-range="today">Hoje</button>
      <button class="btn" data-range="7">7 dias</button>
      <button class="btn" data-range="30">30 dias</button>
      <input type="date" id="custom-start" />
      <input type="date" id="custom-end" />
      <button class="btn" id="apply-custom">Aplicar</button>
    </div>
    <a class="btn" href="/admin/{tenant_id}/menu">Cardápio</a>
    <a class="btn" href="/admin/{tenant_id}/modifiers">Adicionais</a>
  </div>
</header>
<main>
  <section class="cards">
    <div class="card">
      <h3>Vendas no período</h3>
      <strong id="gross-sales">R$ 0,00</strong>
      <span class="muted" id="orders-count">0 pedidos</span>
    </div>
    <div class="card">
      <h3>Entradas - Saídas</h3>
      <strong id="net-cash">R$ 0,00</strong>
      <span class="muted">Saldo líquido</span>
    </div>
    <div class="card">
      <h3>Pedidos</h3>
      <strong id="orders-total">0</strong>
      <span class="muted" id="orders-breakdown">0 pagos • 0 em aberto</span>
    </div>
    <div class="card">
      <h3>Ticket médio</h3>
      <strong id="avg-ticket">R$ 0,00</strong>
      <span class="muted">Média por pedido</span>
    </div>
  </section>

  <section class="grid">
    <div class="chart-card">
      <div class="chart-header">
        <div>
          <strong>Vendas por dia</strong>
          <div class="muted" id="chart-subtitle">Últimos dias</div>
        </div>
        <span class="pill" id="last-updated">Atualizado</span>
      </div>
      <canvas id="sales-chart" width="800" height="240"></canvas>
    </div>
    <div class="section-card">
      <strong>Forma de pagamento</strong>
      <div class="muted" style="margin:6px 0 12px;">Contribuição no período</div>
      <div class="list" id="payment-breakdown"></div>
    </div>
  </section>

  <section class="grid">
    <div class="section-card">
      <strong>Top itens vendidos</strong>
      <div class="muted" style="margin:6px 0 12px;">Mais vendidos no período</div>
      <table>
        <thead>
          <tr>
            <th>Item</th>
            <th>Qtd</th>
            <th>Total</th>
          </tr>
        </thead>
        <tbody id="top-items"></tbody>
      </table>
    </div>
    <div class="section-card">
      <strong>Pedidos recentes</strong>
      <div class="muted" style="margin:6px 0 12px;">Últimos pedidos</div>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Status</th>
            <th>Total</th>
            <th>Pagamento</th>
          </tr>
        </thead>
        <tbody id="recent-orders"></tbody>
      </table>
    </div>
  </section>
</main>
<script>
  const TENANT_ID = {tenant_id};
  const statusEl = document.getElementById('status');
  const grossSalesEl = document.getElementById('gross-sales');
  const netCashEl = document.getElementById('net-cash');
  const ordersCountEl = document.getElementById('orders-count');
  const ordersTotalEl = document.getElementById('orders-total');
  const ordersBreakdownEl = document.getElementById('orders-breakdown');
  const avgTicketEl = document.getElementById('avg-ticket');
  const chartSubtitleEl = document.getElementById('chart-subtitle');
  const lastUpdatedEl = document.getElementById('last-updated');
  const paymentBreakdownEl = document.getElementById('payment-breakdown');
  const topItemsEl = document.getElementById('top-items');
  const recentOrdersEl = document.getElementById('recent-orders');
  const rangeButtons = Array.from(document.querySelectorAll('[data-range]'));
  const customStartInput = document.getElementById('custom-start');
  const customEndInput = document.getElementById('custom-end');
  const applyCustomButton = document.getElementById('apply-custom');

  let selectedRange = 'today';
  const todayDefault = new Date();
  customStartInput.value = formatDate(todayDefault);
  customEndInput.value = formatDate(todayDefault);

  function formatCurrency(value) {{
    const cents = Number(value || 0);
    return (cents / 100).toLocaleString('pt-BR', {{ style: 'currency', currency: 'BRL' }});
  }}

  function formatDate(date) {{
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${{year}}-${{month}}-${{day}}`;
  }}

  function buildRange() {{
    const today = new Date();
    if (selectedRange === 'today') {{
      const date = formatDate(today);
      return {{ de: date, para: date, label: 'Hoje' }};
    }}
    if (selectedRange === 'custom') {{
      const de = customStartInput.value || formatDate(today);
      const para = customEndInput.value || formatDate(today);
      return {{ de, para, label: 'Personalizado' }};
    }}
    const days = Number(selectedRange);
    const start = new Date(today);
    start.setDate(today.getDate() - (days - 1));
    return {{ de: formatDate(start), para: formatDate(today), label: `Últimos ${{days}} dias` }};
  }}

  async function fetchJson(url) {{
    const response = await fetch(url);
    if (!response.ok) {{
      let detail = 'Erro ao carregar dados.';
      try {{
        const data = await response.json();
        if (data && data.detail) detail = data.detail;
      }} catch (err) {{
        // ignore
      }}
      throw new Error(detail);
    }}
    return response.json();
  }}

  function setStatus(message) {{
    statusEl.textContent = message;
  }}

  function updateBreakdown(items) {{
    paymentBreakdownEl.innerHTML = '';
    if (!items.length) {{
      paymentBreakdownEl.innerHTML = '<div class="muted">Nenhum pagamento no período.</div>';
      return;
    }}
    items.forEach((item) => {{
      const row = document.createElement('div');
      row.className = 'list-item';
      row.innerHTML = `
        <div>
          <strong>${{item.method || 'outros'}}</strong>
          <div class="muted">${{item.count}} transações</div>
        </div>
        <div>${{formatCurrency(item.total_cents)}}</div>
      `;
      paymentBreakdownEl.appendChild(row);
    }});
  }}

  function updateTopItems(items) {{
    topItemsEl.innerHTML = '';
    if (!items.length) {{
      topItemsEl.innerHTML = '<tr><td colspan="3" class="muted">Nenhum item no período.</td></tr>';
      return;
    }}
    items.forEach((item) => {{
      const row = document.createElement('tr');
      row.innerHTML = `
        <td>${{item.name}}</td>
        <td>${{item.qty}}</td>
        <td>${{formatCurrency(item.total_cents)}}</td>
      `;
      topItemsEl.appendChild(row);
    }});
  }}

  function updateRecentOrders(orders) {{
    recentOrdersEl.innerHTML = '';
    if (!orders.length) {{
      recentOrdersEl.innerHTML = '<tr><td colspan="4" class="muted">Nenhum pedido recente.</td></tr>';
      return;
    }}
    orders.forEach((order) => {{
      const row = document.createElement('tr');
      const paymentLabel = `${{order.payment_method || '—'}} • ${{order.payment_status}}`;
      row.innerHTML = `
        <td>#${{order.id}}</td>
        <td>${{order.status}}</td>
        <td>${{formatCurrency(order.total_cents)}}</td>
        <td>${{paymentLabel}}</td>
      `;
      recentOrdersEl.appendChild(row);
    }});
  }}

  function renderChart(points) {{
    const canvas = document.getElementById('sales-chart');
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    ctx.clearRect(0, 0, width, height);
    ctx.strokeStyle = 'rgba(255,255,255,0.1)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(40, 10);
    ctx.lineTo(40, height - 30);
    ctx.lineTo(width - 10, height - 30);
    ctx.stroke();

    if (!points.length) return;

    const values = points.map((point) => point.gross_sales_cents);
    const maxValue = Math.max(...values, 1);
    const stepX = (width - 60) / Math.max(points.length - 1, 1);

    ctx.strokeStyle = '#ff8a4c';
    ctx.lineWidth = 2;
    ctx.beginPath();
    points.forEach((point, index) => {{
      const x = 40 + stepX * index;
      const y = height - 30 - (point.gross_sales_cents / maxValue) * (height - 60);
      if (index === 0) {{
        ctx.moveTo(x, y);
      }} else {{
        ctx.lineTo(x, y);
      }}
    }});
    ctx.stroke();

    ctx.fillStyle = '#91a4b7';
    ctx.font = '11px sans-serif';
    points.forEach((point, index) => {{
      if (index % Math.ceil(points.length / 6) === 0 || index === points.length - 1) {{
        const x = 40 + stepX * index;
        ctx.fillText(point.date.slice(5), x - 12, height - 10);
      }}
    }});
  }}

  async function loadDashboard() {{
    try {{
      setStatus('Atualizando…');
      const range = buildRange();
      chartSubtitleEl.textContent = range.label;
      const query = `tenant_id=${{TENANT_ID}}&de=${{range.de}}&para=${{range.para}}`;
      const [overview, timeseries, topItems, recentOrders] = await Promise.all([
        fetchJson(`/api/dashboard/overview?${{query}}`),
        fetchJson(`/api/dashboard/timeseries?${{query}}&bucket=day`),
        fetchJson(`/api/dashboard/top-items?${{query}}&limit=10`),
        fetchJson(`/api/dashboard/recent-orders?tenant_id=${{TENANT_ID}}&limit=20`),
      ]);

      grossSalesEl.textContent = formatCurrency(overview.gross_sales_cents);
      netCashEl.textContent = formatCurrency(overview.net_cash_cents);
      ordersCountEl.textContent = `${{overview.orders_count}} pedidos`;
      ordersTotalEl.textContent = overview.orders_count;
      ordersBreakdownEl.textContent = `${{overview.paid_orders_count}} pagos • ${{overview.open_orders_count}} em aberto`;
      avgTicketEl.textContent = formatCurrency(overview.avg_ticket_cents);
      lastUpdatedEl.textContent = `Atualizado ${new Date(overview.last_updated).toLocaleTimeString('pt-BR')}`;
      updateBreakdown(overview.payment_method_breakdown || []);
      renderChart(timeseries.points || []);
      updateTopItems(topItems.items || []);
      updateRecentOrders(recentOrders.orders || []);
      setStatus('Pronto');
    }} catch (err) {{
      setStatus(err.message || 'Erro ao carregar.');
    }}
  }}

  rangeButtons.forEach((button) => {{
    button.addEventListener('click', () => {{
      rangeButtons.forEach((btn) => btn.classList.remove('active'));
      button.classList.add('active');
      selectedRange = button.dataset.range || 'today';
      loadDashboard();
    }});
  }});

  applyCustomButton.addEventListener('click', () => {{
    rangeButtons.forEach((btn) => btn.classList.remove('active'));
    selectedRange = 'custom';
    loadDashboard();
  }});

  loadDashboard();
</script>
</body>
</html>
"""
    return HTMLResponse(html)


@router.get("/admin/{tenant_id}/modifiers", response_class=HTMLResponse)
def admin_modifiers(tenant_id: int):
    html = f"""
<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Painel do Dono • Adicionais (Tenant {tenant_id})</title>
  <style>
    :root {{
      --bg: #0b0f14;
      --card: #121826;
      --muted: #91a4b7;
      --text: #e7eef6;
      --border: rgba(255,255,255,0.08);
      --shadow: 0 10px 30px rgba(0,0,0,.35);
      --radius: 14px;
      --accent: #63e6be;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial;
      background: radial-gradient(1000px 700px at 10% 0%, #142136 0%, var(--bg) 60%);
      color: var(--text);
    }}
    header {{
      padding: 18px 22px;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
    }}
    .brand {{ display: flex; align-items: center; gap: 10px; }}
    .logo {{
      width: 34px; height: 34px;
      border-radius: 10px;
      background: linear-gradient(135deg, #63e6be, #4dabf7);
      box-shadow: var(--shadow);
    }}
    .title {{ display: flex; flex-direction: column; line-height: 1.1; }}
    .title b {{ font-size: 16px; }}
    .title span {{ font-size: 12px; color: var(--muted); }}
    .pill {{
      padding: 8px 10px;
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.03);
      border-radius: 999px;
      color: var(--muted);
      font-size: 12px;
    }}
    .btn {{
      cursor: pointer;
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.04);
      color: var(--text);
      padding: 9px 12px;
      border-radius: 10px;
      transition: .15s ease;
    }}
    .btn:hover {{ background: rgba(255,255,255,0.08); }}
    main {{ padding: 18px 18px 26px; }}
    .layout {{ display: grid; grid-template-columns: 280px 1fr; gap: 14px; }}
    .card {{
      background: rgba(255,255,255,0.03);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
    }}
    .section {{ padding: 14px; border-bottom: 1px solid var(--border); }}
    .section:last-child {{ border-bottom: none; }}
    .section h3 {{ margin: 0 0 10px; font-size: 14px; letter-spacing: .3px; }}
    .list {{ display: grid; gap: 8px; }}
    .item {{
      padding: 10px 12px;
      border: 1px solid var(--border);
      border-radius: 10px;
      background: rgba(255,255,255,0.03);
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 10px;
    }}
    .muted {{ color: var(--muted); font-size: 12px; }}
    label {{ font-size: 12px; color: var(--muted); display: block; margin-bottom: 4px; }}
    input {{
      width: 100%;
      background: rgba(255,255,255,0.04);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 8px 10px;
      border-radius: 8px;
      font-size: 13px;
    }}
    .form-grid {{ display: grid; gap: 10px; }}
    .actions {{ display: flex; gap: 8px; flex-wrap: wrap; }}
    @media (max-width: 980px) {{
      .layout {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
<header>
  <div class="brand">
    <div class="logo"></div>
    <div class="title">
      <b>Painel do Dono • Adicionais</b>
      <span>Tenant {tenant_id} • MVP simples</span>
    </div>
  </div>
  <div class="actions">
    <span class="pill" id="status">Carregando…</span>
    <a class="btn" href="/admin/{tenant_id}/dashboard">Dashboard</a>
    <a class="btn" href="/admin/{tenant_id}/menu">Voltar ao cardápio</a>
  </div>
</header>
<main>
  <div class="layout">
    <div class="card">
      <div class="section">
        <h3>Novo grupo</h3>
        <form class="form-grid" onsubmit="event.preventDefault(); createGroup();">
          <div>
            <label for="group-name">Nome do grupo</label>
            <input id="group-name" required />
          </div>
          <div class="actions">
            <button class="btn" type="submit">Criar grupo</button>
          </div>
        </form>
      </div>
      <div class="section">
        <h3>Grupos existentes</h3>
        <div class="list" id="groups"></div>
      </div>
    </div>
    <div class="card">
      <div class="section">
        <h3 id="modifiers-title">Adicionais do grupo</h3>
        <div class="muted" id="group-hint">Selecione um grupo à esquerda.</div>
      </div>
      <div class="section">
        <form class="form-grid" onsubmit="event.preventDefault(); createModifier();">
          <div>
            <label for="modifier-name">Nome do adicional</label>
            <input id="modifier-name" required />
          </div>
          <div>
            <label for="modifier-price">Preço (centavos)</label>
            <input id="modifier-price" type="number" min="0" required />
          </div>
          <div class="actions">
            <button class="btn" type="submit">Criar adicional</button>
          </div>
        </form>
      </div>
      <div class="section">
        <div class="list" id="modifiers"></div>
      </div>
    </div>
  </div>
</main>
<script>
  const TENANT_ID = {tenant_id};
  const statusEl = document.getElementById('status');
  const groupsEl = document.getElementById('groups');
  const modifiersEl = document.getElementById('modifiers');
  const modifiersTitleEl = document.getElementById('modifiers-title');
  const groupHintEl = document.getElementById('group-hint');
  const groupNameInput = document.getElementById('group-name');
  const modifierNameInput = document.getElementById('modifier-name');
  const modifierPriceInput = document.getElementById('modifier-price');

  let selectedGroup = null;

  function formatPrice(value) {{
    const cents = Number(value || 0);
    return (cents / 100).toLocaleString('pt-BR', {{ style: 'currency', currency: 'BRL' }});
  }}

  async function fetchJson(url, options = {{}}) {{
    const response = await fetch(url, {{
      headers: {{ 'Content-Type': 'application/json' }},
      ...options,
    }});
    if (!response.ok) {{
      let detail = 'Erro ao comunicar com a API.';
      try {{
        const data = await response.json();
        if (data && data.detail) detail = data.detail;
      }} catch (err) {{
        // ignore
      }}
      throw new Error(detail);
    }}
    return response.json();
  }}

  function setStatus(message) {{
    statusEl.textContent = message;
  }}

  async function loadGroups() {{
    const groups = await fetchJson(`/api/modifiers/groups/${{TENANT_ID}}`);
    groupsEl.innerHTML = '';
    if (!groups.length) {{
      groupsEl.innerHTML = '<div class="muted">Nenhum grupo cadastrado.</div>';
      return;
    }}
    groups.forEach((group) => {{
      const row = document.createElement('div');
      row.className = 'item';
      row.innerHTML = `
        <div>
          <strong>${{group.name}}</strong><br />
          <small class="muted">ID ${{group.id}}</small>
        </div>
        <button class="btn" onclick="selectGroup(${{group.id}}, '${{group.name.replace(/'/g, "\\'")}}')">Ver</button>
      `;
      groupsEl.appendChild(row);
    }});
  }}

  async function selectGroup(groupId, groupName) {{
    selectedGroup = {{ id: groupId, name: groupName }};
    modifiersTitleEl.textContent = `Adicionais • ${{groupName}}`;
    groupHintEl.textContent = '';
    await loadModifiers();
  }}

  async function loadModifiers() {{
    if (!selectedGroup) return;
    const modifiers = await fetchJson(`/api/modifiers/groups/${{TENANT_ID}}/${{selectedGroup.id}}/modifiers`);
    modifiersEl.innerHTML = '';
    if (!modifiers.length) {{
      modifiersEl.innerHTML = '<div class="muted">Nenhum adicional ainda.</div>';
      return;
    }}
    modifiers.forEach((modifier) => {{
      const row = document.createElement('div');
      row.className = 'item';
      row.innerHTML = `
        <div>
          <strong>${{modifier.name}}</strong><br />
          <small class="muted">${{formatPrice(modifier.price_cents)}}</small>
        </div>
        <span class="pill">ID ${{modifier.id}}</span>
      `;
      modifiersEl.appendChild(row);
    }});
  }}

  async function createGroup() {{
    try {{
      setStatus('Criando grupo…');
      await fetchJson(`/api/modifiers/groups/${{TENANT_ID}}`, {{
        method: 'POST',
        body: JSON.stringify({{ tenant_id: TENANT_ID, name: groupNameInput.value.trim(), active: true }}),
      }});
      groupNameInput.value = '';
      await loadGroups();
      setStatus('Grupo criado.');
    }} catch (err) {{
      setStatus(err.message || 'Erro ao criar grupo.');
    }}
  }}

  async function createModifier() {{
    if (!selectedGroup) {{
      setStatus('Selecione um grupo antes de criar adicionais.');
      return;
    }}
    try {{
      setStatus('Criando adicional…');
      await fetchJson(`/api/modifiers/groups/${{TENANT_ID}}/${{selectedGroup.id}}/modifiers`, {{
        method: 'POST',
        body: JSON.stringify({{
          name: modifierNameInput.value.trim(),
          price_cents: Number(modifierPriceInput.value || 0),
        }}),
      }});
      modifierNameInput.value = '';
      modifierPriceInput.value = '';
      await loadModifiers();
      setStatus('Adicional criado.');
    }} catch (err) {{
      setStatus(err.message || 'Erro ao criar adicional.');
    }}
  }}

  async function init() {{
    try {{
      setStatus('Carregando dados…');
      await loadGroups();
      setStatus('Pronto');
    }} catch (err) {{
      setStatus(err.message || 'Erro ao carregar.');
    }}
  }}

  init();
</script>
</body>
</html>
"""
    return HTMLResponse(html)
