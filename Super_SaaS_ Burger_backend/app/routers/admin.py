from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import ADMIN_SESSION_COOKIE_SECURE, ADMIN_SESSION_MAX_AGE_SECONDS
from app.core.database import get_db
from app.deps import require_role_ui
from app.models.admin_user import AdminUser
from app.services.admin_audit import log_admin_action
from app.services.admin_auth import ADMIN_SESSION_COOKIE, create_admin_session
from app.services.admin_login_attempts import (
    check_login_lock,
    clear_login_attempts,
    register_failed_login,
)
from app.services.passwords import verify_password

router = APIRouter(tags=["admin"])


def _cookie_secure(request: Request | None) -> bool:
    if request and request.url.scheme == "https":
        return True
    return ADMIN_SESSION_COOKIE_SECURE


def _login_html(error: str | None = None) -> str:
    error_html = f"<div class='error'>{error}</div>" if error else ""
    return f"""<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Admin Login</title>
  <style>
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial;
      background: radial-gradient(1000px 700px at 10% 0%, #142136 0%, #0b0f14 60%);
      color: #e7eef6;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      padding: 20px;
    }}
    .card {{
      width: 100%;
      max-width: 420px;
      background: rgba(255,255,255,0.03);
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 16px;
      padding: 22px;
      box-shadow: 0 10px 30px rgba(0,0,0,.35);
    }}
    h1 {{ font-size: 20px; margin: 0 0 8px; }}
    p {{ color: #91a4b7; margin: 0 0 16px; font-size: 13px; }}
    label {{ display:block; font-size: 12px; color: #91a4b7; margin: 12px 0 6px; }}
    input {{
      width: 100%;
      background: rgba(255,255,255,0.04);
      border: 1px solid rgba(255,255,255,0.08);
      color: #e7eef6;
      padding: 10px 12px;
      border-radius: 10px;
      font-size: 14px;
    }}
    button {{
      margin-top: 16px;
      width: 100%;
      padding: 10px 12px;
      border-radius: 10px;
      border: none;
      background: #ffb86b;
      color: #1a1f2b;
      font-weight: 600;
      cursor: pointer;
    }}
    .hint {{ font-size: 12px; color: #91a4b7; margin-top: 10px; }}
    .error {{
      background: rgba(255,77,109,0.2);
      border: 1px solid rgba(255,77,109,0.4);
      color: #ff9aa2;
      padding: 8px 10px;
      border-radius: 10px;
      margin-top: 12px;
      font-size: 12px;
    }}
  </style>
</head>
<body>
  <div class="card">
    <h1>Login Admin</h1>
    <p>Entre com seu usuário para acessar o painel do restaurante.</p>
    <form method="post" action="/admin/login">
      <label for="tenant_id">Tenant ID</label>
      <input id="tenant_id" name="tenant_id" type="number" min="1" required value="1" />

      <label for="email">E-mail</label>
      <input id="email" name="email" type="email" required />

      <label for="password">Senha</label>
      <input id="password" name="password" type="password" required />

      <button type="submit">Entrar</button>
      {error_html}
      <div class="hint">Em DEV, use admin@local / admin123 e troque depois.</div>
    </form>
  </div>
</body>
</html>"""


@router.get("/admin/login", response_class=HTMLResponse)
def admin_login_page():
    return HTMLResponse(_login_html())


@router.post("/admin/login")
def admin_login(
    tenant_id: int = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    request: Request = None,
    db: Session = Depends(get_db),
):
    locked, _, _ = check_login_lock(db, tenant_id, email)
    if locked:
        user = (
            db.query(AdminUser)
            .filter(
                AdminUser.tenant_id == tenant_id,
                AdminUser.email == email,
            )
            .first()
        )
        log_admin_action(
            db,
            tenant_id=tenant_id,
            user_id=user.id if user else 0,
            action="login_locked",
            entity_type="admin_user",
            entity_id=user.id if user else None,
            meta={"email": email},
        )
        db.commit()
        return HTMLResponse(_login_html("Muitas tentativas. Tente novamente em alguns minutos."), status_code=429)

    user = (
        db.query(AdminUser)
        .filter(
            AdminUser.tenant_id == tenant_id,
            AdminUser.email == email,
        )
        .first()
    )
    if not user or not user.active or not verify_password(password, user.password_hash):
        _, locked_after = register_failed_login(db, tenant_id, email)
        log_admin_action(
            db,
            tenant_id=tenant_id,
            user_id=user.id if user else 0,
            action="login_failed",
            entity_type="admin_user",
            entity_id=user.id if user else None,
            meta={"email": email},
        )
        if locked_after:
            log_admin_action(
                db,
                tenant_id=tenant_id,
                user_id=user.id if user else 0,
                action="login_locked",
                entity_type="admin_user",
                entity_id=user.id if user else None,
                meta={"email": email},
            )
        db.commit()
        if locked_after:
            return HTMLResponse(_login_html("Muitas tentativas. Tente novamente em alguns minutos."), status_code=429)
        return HTMLResponse(_login_html("Credenciais inválidas"), status_code=401)

    token = create_admin_session({"user_id": user.id, "tenant_id": user.tenant_id, "role": user.role})
    response = RedirectResponse(url=f"/admin/{tenant_id}/dashboard", status_code=303)
    response.set_cookie(
        ADMIN_SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        max_age=ADMIN_SESSION_MAX_AGE_SECONDS,
        secure=_cookie_secure(request),
    )
    clear_login_attempts(db, tenant_id, email)
    log_admin_action(
        db,
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="login_success",
    )
    db.commit()
    return response


@router.get("/admin/logout")
def admin_logout(request: Request):
    response = RedirectResponse(url="/admin/login", status_code=303)
    response.delete_cookie(
        ADMIN_SESSION_COOKIE,
        samesite="lax",
        secure=_cookie_secure(request),
    )
    return response


@router.get("/admin/{tenant_id}/menu", response_class=HTMLResponse)
def admin_menu(
    tenant_id: int,
    _user: AdminUser = Depends(require_role_ui(["admin"])),
):
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
    <a class="btn" href="/admin/{tenant_id}/reports">Relatórios</a>
    <a class="btn" href="/admin/{tenant_id}/modifiers">Gerenciar adicionais</a>
    <a class="btn" href="/admin/{tenant_id}/inventory/items">Estoque</a>
    <a class="btn" href="/admin/{tenant_id}/users">Usuários</a>
    <a class="btn" href="/admin/{tenant_id}/audit">Auditoria</a>
    <a class="btn" href="/admin/logout">Logout</a>
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
def admin_dashboard(
    tenant_id: int,
    _user: AdminUser = Depends(require_role_ui(["admin", "operator", "cashier"])),
):
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
      grid-template-columns: repeat(6, minmax(180px, 1fr));
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
      .cards {{ grid-template-columns: repeat(3, minmax(180px, 1fr)); }}
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
    <a class="btn" href="/admin/{tenant_id}/reports">Relatórios</a>
    <a class="btn" href="/admin/{tenant_id}/modifiers">Adicionais</a>
    <a class="btn" href="/admin/{tenant_id}/inventory/items">Estoque</a>
    <a class="btn" href="/admin/{tenant_id}/users">Usuários</a>
    <a class="btn" href="/admin/{tenant_id}/audit">Auditoria</a>
    <a class="btn" href="/admin/logout">Logout</a>
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
    <div class="card">
      <h3>COGS</h3>
      <strong id="cogs">R$ 0,00</strong>
      <span class="muted">Custo das mercadorias</span>
    </div>
    <div class="card">
      <h3>Lucro bruto</h3>
      <strong id="gross-profit">R$ 0,00</strong>
      <span class="muted">Receita - COGS</span>
    </div>
    <div class="card">
      <h3>Baixo estoque</h3>
      <strong id="low-stock">0</strong>
      <span class="muted">Itens abaixo do mínimo</span>
    </div>
  </section>

  <section class="grid">
    <div class="chart-card">
      <div class="chart-header">
        <div>
          <strong>Vendas por dia</strong>
          <div class="muted" id="chart-subtitle">Últimos dias</div>
        </div>
        <span class="pill" id="last-updated">Última atualização: -</span>
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
  const cogsEl = document.getElementById('cogs');
  const grossProfitEl = document.getElementById('gross-profit');
  const lowStockEl = document.getElementById('low-stock');
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
      cogsEl.textContent = formatCurrency(overview.cogs_cents);
      grossProfitEl.textContent = formatCurrency(overview.gross_profit_cents);
      lowStockEl.textContent = overview.low_stock_count ?? 0;
      const lastUpdatedLabel = overview.last_updated_str || "-";
      lastUpdatedEl.textContent = "Última atualização: " + lastUpdatedLabel;
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


@router.get("/admin/{tenant_id}/reports", response_class=HTMLResponse)
def admin_reports(
    tenant_id: int,
    _user: AdminUser = Depends(require_role_ui(["admin", "operator", "cashier"])),
):
    html = f"""
<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Painel do Dono • Relatórios (Tenant {tenant_id})</title>
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
      grid-template-columns: repeat(7, minmax(170px, 1fr));
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
    @media (max-width: 1200px) {{
      .cards {{ grid-template-columns: repeat(3, minmax(180px, 1fr)); }}
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
      <b>Relatórios</b>
      <span>Tenant {tenant_id} • visão financeira</span>
    </div>
  </div>
  <div class="actions">
    <span class="pill" id="status">Carregando…</span>
    <div class="filters">
      <button class="btn active" data-range="1">Hoje</button>
      <button class="btn" data-range="7">7 dias</button>
      <button class="btn" data-range="30">30 dias</button>
      <input type="date" id="custom-start" />
      <input type="date" id="custom-end" />
      <button class="btn" id="apply-custom">Aplicar</button>
    </div>
    <a class="btn" href="/admin/{tenant_id}/dashboard">Dashboard</a>
    <a class="btn" href="/admin/{tenant_id}/menu">Cardápio</a>
    <a class="btn" href="/admin/{tenant_id}/inventory/items">Estoque</a>
    <a class="btn" href="/admin/{tenant_id}/users">Usuários</a>
    <a class="btn" href="/admin/{tenant_id}/audit">Auditoria</a>
    <a class="btn" href="/admin/logout">Logout</a>
  </div>
</header>
<main>
  <section class="cards">
    <div class="card">
      <h3>Receita bruta</h3>
      <strong id="gross-revenue">R$ 0,00</strong>
      <span class="muted">Total recebido</span>
    </div>
    <div class="card">
      <h3>Taxas</h3>
      <strong id="fees">R$ 0,00</strong>
      <span class="muted">Meios de pagamento</span>
    </div>
    <div class="card">
      <h3>Receita líquida</h3>
      <strong id="net-revenue">R$ 0,00</strong>
      <span class="muted">Bruta - taxas</span>
    </div>
    <div class="card">
      <h3>CMV (COGS)</h3>
      <strong id="cogs">R$ 0,00</strong>
      <span class="muted" id="cogs-note">Custo do período</span>
    </div>
    <div class="card">
      <h3>Lucro bruto</h3>
      <strong id="gross-profit">R$ 0,00</strong>
      <span class="muted">Líquida - CMV</span>
    </div>
    <div class="card">
      <h3>Pedidos</h3>
      <strong id="orders-count">0</strong>
      <span class="muted">Pagos no período</span>
    </div>
    <div class="card">
      <h3>Ticket médio</h3>
      <strong id="avg-ticket">R$ 0,00</strong>
      <span class="muted">Receita líquida / pedidos</span>
    </div>
  </section>

  <section class="section-card">
    <div class="actions" style="justify-content: space-between;">
      <div>
        <strong>Top itens vendidos</strong>
        <div class="muted" style="margin-top: 6px;">Mais vendidos no período</div>
      </div>
      <div class="actions">
        <button class="btn" id="export-financial">Exportar CSV financeiro</button>
        <button class="btn" id="export-items">Exportar CSV top itens</button>
      </div>
    </div>
    <table>
      <thead>
        <tr>
          <th>Item</th>
          <th>Qtd</th>
          <th>Bruta</th>
          <th>Líquida</th>
          <th>CMV</th>
          <th>Lucro</th>
        </tr>
      </thead>
      <tbody id="top-items"></tbody>
    </table>
  </section>
</main>
<script>
  const TENANT_ID = {tenant_id};
  const statusEl = document.getElementById('status');
  const grossRevenueEl = document.getElementById('gross-revenue');
  const feesEl = document.getElementById('fees');
  const netRevenueEl = document.getElementById('net-revenue');
  const cogsEl = document.getElementById('cogs');
  const cogsNoteEl = document.getElementById('cogs-note');
  const grossProfitEl = document.getElementById('gross-profit');
  const ordersCountEl = document.getElementById('orders-count');
  const avgTicketEl = document.getElementById('avg-ticket');
  const topItemsEl = document.getElementById('top-items');
  const startInput = document.getElementById('custom-start');
  const endInput = document.getElementById('custom-end');
  const applyBtn = document.getElementById('apply-custom');
  const exportFinancialBtn = document.getElementById('export-financial');
  const exportItemsBtn = document.getElementById('export-items');

  function formatCurrency(value) {{
    const cents = Number(value || 0);
    return (cents / 100).toLocaleString('pt-BR', {{ style: 'currency', currency: 'BRL' }});
  }}

  function setStatus(message) {{
    statusEl.textContent = message;
  }}

  function formatDateInput(date) {{
    return date.toISOString().slice(0, 10);
  }}

  async function fetchJson(url) {{
    const response = await fetch(url, {{ headers: {{ 'Content-Type': 'application/json' }} }});
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

  function buildQuery() {{
    const start = startInput.value;
    const end = endInput.value;
    if (!start || !end) {{
      return null;
    }}
    return `tenant_id=${{TENANT_ID}}&from=${{start}}&to=${{end}}`;
  }}

  function setRange(days) {{
    const today = new Date();
    const startDate = new Date();
    startDate.setDate(today.getDate() - (days - 1));
    startInput.value = formatDateInput(startDate);
    endInput.value = formatDateInput(today);
  }}

  async function loadReports() {{
    const query = buildQuery();
    if (!query) {{
      return;
    }}
    try {{
      setStatus('Carregando…');
      const [summary, topItems] = await Promise.all([
        fetchJson(`/api/reports/financial/summary?${{query}}`),
        fetchJson(`/api/reports/sales/top-items?${{query}}&limit=20`),
      ]);

      grossRevenueEl.textContent = formatCurrency(summary.gross_revenue_cents);
      feesEl.textContent = formatCurrency(summary.fees_cents);
      netRevenueEl.textContent = formatCurrency(summary.net_revenue_cents);
      cogsEl.textContent = formatCurrency(summary.cogs_cents);
      grossProfitEl.textContent = formatCurrency(summary.gross_profit_cents);
      ordersCountEl.textContent = summary.orders_count || 0;
      avgTicketEl.textContent = formatCurrency(summary.avg_ticket_cents);
      cogsNoteEl.textContent = summary.cogs_available ? 'Custo do período' : 'COGS indisponível no período';

      topItemsEl.innerHTML = '';
      if (!topItems.items || !topItems.items.length) {{
        topItemsEl.innerHTML = '<tr><td colspan=\"6\" class=\"muted\">Nenhum item no período.</td></tr>';
      }} else {{
        topItems.items.forEach((item) => {{
          const row = document.createElement('tr');
          row.innerHTML = `
            <td><strong>${{item.item_name}}</strong></td>
            <td>${{item.qty}}</td>
            <td>${{formatCurrency(item.gross_revenue_cents)}}</td>
            <td>${{formatCurrency(item.net_revenue_cents)}}</td>
            <td>${{formatCurrency(item.cogs_cents)}}</td>
            <td>${{formatCurrency(item.gross_profit_cents)}}</td>
          `;
          topItemsEl.appendChild(row);
        }});
      }}

      setStatus('Pronto');
    }} catch (err) {{
      setStatus(err.message || 'Erro ao carregar.');
    }}
  }}

  function setActiveButton(target) {{
    document.querySelectorAll('[data-range]').forEach((btn) => {{
      btn.classList.toggle('active', btn === target);
    }});
  }}

  document.querySelectorAll('[data-range]').forEach((btn) => {{
    btn.addEventListener('click', () => {{
      const days = Number(btn.dataset.range || 1);
      setRange(days);
      setActiveButton(btn);
      loadReports();
    }});
  }});

  applyBtn.addEventListener('click', () => {{
    setActiveButton(null);
    loadReports();
  }});

  exportFinancialBtn.addEventListener('click', () => {{
    const query = buildQuery();
    if (!query) return;
    window.location.href = `/api/reports/export/financial.csv?${{query}}`;
  }});

  exportItemsBtn.addEventListener('click', () => {{
    const query = buildQuery();
    if (!query) return;
    window.location.href = `/api/reports/export/top-items.csv?${{query}}&limit=50`;
  }});

  setRange(7);
  loadReports();
</script>
</body>
</html>
"""
    return HTMLResponse(html)


@router.get("/admin/{tenant_id}/modifiers", response_class=HTMLResponse)
def admin_modifiers(
    tenant_id: int,
    _user: AdminUser = Depends(require_role_ui(["admin", "operator"])),
):
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
    <a class="btn" href="/admin/{tenant_id}/reports">Relatórios</a>
    <a class="btn" href="/admin/{tenant_id}/menu">Voltar ao cardápio</a>
    <a class="btn" href="/admin/{tenant_id}/inventory/items">Estoque</a>
    <a class="btn" href="/admin/{tenant_id}/users">Usuários</a>
    <a class="btn" href="/admin/{tenant_id}/audit">Auditoria</a>
    <a class="btn" href="/admin/logout">Logout</a>
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


@router.get("/admin/{tenant_id}/inventory/items", response_class=HTMLResponse)
def admin_inventory_items(
    tenant_id: int,
    _user: AdminUser = Depends(require_role_ui(["admin"])),
):
    html = """
<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Painel do Dono • Estoque (Tenant __TENANT_ID__)</title>
  <style>
    :root {
      --bg: #0b0f14;
      --card: #121826;
      --muted: #91a4b7;
      --text: #e7eef6;
      --border: rgba(255,255,255,0.08);
      --shadow: 0 10px 30px rgba(0,0,0,.35);
      --radius: 14px;
      --accent: #ffb86b;
      --danger: #ff6b6b;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial;
      background: radial-gradient(1000px 700px at 10% 0%, #142136 0%, var(--bg) 60%);
      color: var(--text);
    }
    header {
      padding: 18px 22px;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }
    .brand { display: flex; align-items: center; gap: 10px; }
    .logo {
      width: 34px; height: 34px;
      border-radius: 10px;
      background: linear-gradient(135deg, #ffb86b, #ff4d6d);
      box-shadow: var(--shadow);
    }
    .title { display: flex; flex-direction: column; line-height: 1.1; }
    .title b { font-size: 16px; }
    .title span { font-size: 12px; color: var(--muted); }
    .pill {
      padding: 8px 10px;
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.03);
      border-radius: 999px;
      color: var(--muted);
      font-size: 12px;
    }
    .btn {
      cursor: pointer;
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.04);
      color: var(--text);
      padding: 9px 12px;
      border-radius: 10px;
      transition: .15s ease;
      font-size: 12px;
    }
    .btn:hover { background: rgba(255,255,255,0.08); }
    main { padding: 18px; }
    .layout { display: grid; grid-template-columns: 1.2fr 1fr; gap: 14px; }
    .card {
      background: rgba(255,255,255,0.03);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
    }
    .section { padding: 14px; border-bottom: 1px solid var(--border); }
    .section:last-child { border-bottom: none; }
    .section h3 { margin: 0 0 10px; font-size: 14px; letter-spacing: .3px; }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }
    th, td {
      padding: 8px 10px;
      text-align: left;
      border-bottom: 1px solid var(--border);
    }
    th { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .4px; }
    label { font-size: 12px; color: var(--muted); display: block; margin-bottom: 4px; }
    input, select {
      width: 100%;
      background: rgba(255,255,255,0.04);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 8px 10px;
      border-radius: 8px;
      font-size: 13px;
    }
    .form-grid { display: grid; gap: 10px; }
    .actions { display: flex; gap: 8px; flex-wrap: wrap; }
    .muted { color: var(--muted); font-size: 12px; }
    .tag {
      font-size: 11px;
      padding: 4px 8px;
      border-radius: 999px;
      background: rgba(255,184,107,0.18);
      color: var(--accent);
      border: 1px solid rgba(255,184,107,0.3);
    }
    .tag.danger {
      background: rgba(255,107,107,0.18);
      color: var(--danger);
      border-color: rgba(255,107,107,0.4);
    }
    @media (max-width: 980px) {
      .layout { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
<header>
  <div class="brand">
    <div class="logo"></div>
    <div class="title">
      <b>Estoque</b>
      <span>Tenant __TENANT_ID__ • Itens e níveis</span>
    </div>
  </div>
  <div class="actions">
    <span class="pill" id="status">Carregando…</span>
    <a class="btn" href="/admin/__TENANT_ID__/dashboard">Dashboard</a>
    <a class="btn" href="/admin/__TENANT_ID__/reports">Relatórios</a>
    <a class="btn" href="/admin/__TENANT_ID__/inventory/movements">Movimentos</a>
    <a class="btn" href="/admin/__TENANT_ID__/inventory/recipes">Receitas</a>
    <a class="btn" href="/admin/__TENANT_ID__/users">Usuários</a>
    <a class="btn" href="/admin/__TENANT_ID__/audit">Auditoria</a>
    <a class="btn" href="/admin/logout">Logout</a>
  </div>
</header>
<main>
  <div class="layout">
    <div class="card">
      <div class="section">
        <h3>Itens em estoque</h3>
        <table>
          <thead>
            <tr>
              <th>Item</th>
              <th>Unidade</th>
              <th>Custo</th>
              <th>Estoque</th>
              <th>Mínimo</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody id="items-table"></tbody>
        </table>
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
            <label for="unit">Unidade</label>
            <input id="unit" placeholder="g, ml, un" required />
          </div>
          <div>
            <label for="cost">Custo unitário (centavos)</label>
            <input id="cost" type="number" min="0" value="0" />
          </div>
          <div>
            <label for="stock">Estoque atual</label>
            <input id="stock" type="number" min="0" step="0.01" value="0" />
          </div>
          <div>
            <label for="min-stock">Mínimo</label>
            <input id="min-stock" type="number" min="0" step="0.01" value="0" />
          </div>
          <div>
            <label for="active">Ativo</label>
            <select id="active">
              <option value="true">Sim</option>
              <option value="false">Não</option>
            </select>
          </div>
          <div class="actions">
            <button class="btn" type="submit">Salvar</button>
            <button class="btn" type="button" onclick="resetForm()">Limpar</button>
          </div>
        </form>
        <div class="muted" id="form-status"></div>
      </div>
    </div>
  </div>
</main>
<script>
  const TENANT_ID = Number('__TENANT_ID__');
  const statusEl = document.getElementById('status');
  const itemsTableEl = document.getElementById('items-table');
  const formTitleEl = document.getElementById('form-title');
  const formStatusEl = document.getElementById('form-status');
  const nameInput = document.getElementById('name');
  const unitInput = document.getElementById('unit');
  const costInput = document.getElementById('cost');
  const stockInput = document.getElementById('stock');
  const minStockInput = document.getElementById('min-stock');
  const activeInput = document.getElementById('active');

  let editingItem = null;

  async function fetchJson(url, options) {
    const response = await fetch(url, options);
    if (!response.ok) {
      let detail = 'Erro ao carregar dados.';
      try {
        const data = await response.json();
        if (data && data.detail) detail = data.detail;
      } catch (err) {
        // ignore
      }
      throw new Error(detail);
    }
    return response.json();
  }

  function formatCurrency(value) {
    const cents = Number(value || 0);
    return (cents / 100).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
  }

  function setStatus(message) {
    statusEl.textContent = message;
  }

  function resetForm() {
    editingItem = null;
    formTitleEl.textContent = 'Criar item';
    formStatusEl.textContent = '';
    nameInput.value = '';
    unitInput.value = '';
    costInput.value = 0;
    stockInput.value = 0;
    minStockInput.value = 0;
    activeInput.value = 'true';
  }

  function renderItems(items) {
    itemsTableEl.innerHTML = '';
    if (!items.length) {
      itemsTableEl.innerHTML = '<tr><td colspan="7" class="muted">Nenhum item cadastrado.</td></tr>';
      return;
    }
    items.forEach((item) => {
      const lowStock = Number(item.current_stock) < Number(item.min_stock_level || 0);
      const row = document.createElement('tr');
      row.innerHTML = `
        <td><strong>${item.name}</strong></td>
        <td>${item.unit}</td>
        <td>${formatCurrency(item.cost_cents)}</td>
        <td>${item.current_stock}</td>
        <td>${item.min_stock_level}</td>
        <td>${lowStock ? '<span class="tag danger">Baixo</span>' : '<span class="tag">Ok</span>'}</td>
        <td><button class="btn" data-id="${item.id}">Editar</button></td>
      `;
      row.querySelector('button').addEventListener('click', () => startEdit(item));
      itemsTableEl.appendChild(row);
    });
  }

  function startEdit(item) {
    editingItem = item;
    formTitleEl.textContent = `Editar: ${item.name}`;
    nameInput.value = item.name;
    unitInput.value = item.unit;
    costInput.value = item.cost_cents;
    stockInput.value = item.current_stock;
    minStockInput.value = item.min_stock_level;
    activeInput.value = item.active ? 'true' : 'false';
  }

  async function loadItems() {
    const items = await fetchJson(`/api/inventory/items?tenant_id=${TENANT_ID}`);
    renderItems(items);
  }

  async function saveItem() {
    try {
      formStatusEl.textContent = '';
      const payload = {
        name: nameInput.value.trim(),
        unit: unitInput.value.trim(),
        cost_cents: Number(costInput.value || 0),
        current_stock: Number(stockInput.value || 0),
        min_stock_level: Number(minStockInput.value || 0),
        active: activeInput.value === 'true',
      };
      if (!payload.name || !payload.unit) {
        throw new Error('Nome e unidade são obrigatórios.');
      }
      if (editingItem) {
        await fetchJson(`/api/inventory/items/${editingItem.id}?tenant_id=${TENANT_ID}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
      } else {
        await fetchJson(`/api/inventory/items?tenant_id=${TENANT_ID}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
      }
      await loadItems();
      resetForm();
      formStatusEl.textContent = 'Salvo com sucesso.';
    } catch (err) {
      formStatusEl.textContent = err.message || 'Erro ao salvar.';
    }
  }

  async function init() {
    try {
      setStatus('Carregando itens…');
      await loadItems();
      resetForm();
      setStatus('Pronto');
    } catch (err) {
      setStatus(err.message || 'Erro ao carregar.');
    }
  }

  init();
</script>
</body>
</html>
"""
    return HTMLResponse(html.replace("__TENANT_ID__", str(tenant_id)))


@router.get("/admin/{tenant_id}/users", response_class=HTMLResponse)
def admin_users_page(
    tenant_id: int,
    _user: AdminUser = Depends(require_role_ui(["admin"])),
):
    html = f"""
<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Admin • Usuários (Tenant {tenant_id})</title>
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
      --danger: #ff6b6b;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial;
      background: radial-gradient(1100px 700px at 10% 0%, #18253a 0%, var(--bg) 60%);
      color: var(--text);
    }}
    header {{
      padding: 18px 22px;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
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
      padding: 6px 10px;
      border-radius: 999px;
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.04);
      font-size: 11px;
      color: var(--muted);
    }}
    .btn {{
      cursor: pointer;
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.04);
      color: var(--text);
      padding: 8px 12px;
      border-radius: 10px;
      transition: .15s ease;
      font-size: 12px;
    }}
    .btn:hover {{ background: rgba(255,255,255,0.08); }}
    .btn.secondary {{ border-color: rgba(255,255,255,0.2); }}
    .btn.danger {{ border-color: rgba(255,107,107,0.45); color: var(--danger); }}
    main {{ padding: 18px; display: grid; gap: 16px; }}
    .card {{
      background: rgba(255,255,255,0.03);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
    }}
    .section {{ padding: 14px; border-bottom: 1px solid var(--border); }}
    .section:last-child {{ border-bottom: none; }}
    h3 {{ margin: 0 0 10px; font-size: 14px; }}
    .form-grid {{ display: grid; gap: 10px; }}
    label {{ font-size: 12px; color: var(--muted); display: block; margin-bottom: 4px; }}
    input, select {{
      width: 100%;
      background: rgba(255,255,255,0.04);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 8px 10px;
      border-radius: 8px;
      font-size: 13px;
    }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{
      padding: 8px 10px;
      border-bottom: 1px solid var(--border);
      text-align: left;
    }}
    th {{ font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: .4px; }}
    .grid {{ display: grid; grid-template-columns: 1fr 1.5fr; gap: 16px; }}
    .status {{ font-size: 12px; color: var(--muted); }}
    @media (max-width: 980px) {{
      .grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
<header>
  <div class="brand">
    <div class="logo"></div>
    <div class="title">
      <b>Usuários Admin</b>
      <span>Tenant {tenant_id} • gerenciamento interno</span>
    </div>
  </div>
  <div class="actions">
    <a class="btn" href="/admin/{tenant_id}/dashboard">Dashboard</a>
    <a class="btn" href="/admin/{tenant_id}/reports">Relatórios</a>
    <a class="btn" href="/admin/{tenant_id}/audit">Auditoria</a>
    <a class="btn" href="/admin/logout">Logout</a>
  </div>
</header>
<main>
  <div class="grid">
    <div class="card">
      <div class="section">
        <h3>Criar usuário</h3>
        <form id="create-form" class="form-grid">
          <div>
            <label for="create-name">Nome</label>
            <input id="create-name" required />
          </div>
          <div>
            <label for="create-email">E-mail</label>
            <input id="create-email" type="email" required />
          </div>
          <div>
            <label for="create-role">Role</label>
            <select id="create-role">
              <option value="admin">admin</option>
              <option value="operator">operator</option>
              <option value="cashier">cashier</option>
            </select>
          </div>
          <div>
            <label for="create-password">Senha inicial</label>
            <input id="create-password" type="password" minlength="6" required />
          </div>
          <div class="actions">
            <button class="btn" type="submit">Criar usuário</button>
          </div>
          <div class="status" id="create-status"></div>
        </form>
      </div>
    </div>
    <div class="card">
      <div class="section">
        <h3>Usuários do tenant</h3>
        <div class="status" id="list-status">Carregando…</div>
      </div>
      <div class="section">
        <table>
          <thead>
            <tr>
              <th>Nome</th>
              <th>Email</th>
              <th>Role</th>
              <th>Ativo</th>
              <th></th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody id="users-table"></tbody>
        </table>
      </div>
    </div>
  </div>
</main>
<script>
  const TENANT_ID = {tenant_id};
  const usersTable = document.getElementById('users-table');
  const listStatus = document.getElementById('list-status');
  const createForm = document.getElementById('create-form');
  const createStatus = document.getElementById('create-status');
  let currentUserId = null;

  function escapeHtml(value) {{
    return (value || '').replace(/[&<>\"']/g, (char) => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;',
    }}[char]));
  }}

  async function fetchJson(url, options = {{}}) {{
    const response = await fetch(url, {{
      headers: {{ 'Content-Type': 'application/json' }},
      credentials: 'same-origin',
      ...options,
    }});
    if (!response.ok) {{
      let detail = 'Erro ao processar.';
      try {{
        const data = await response.json();
        detail = data.detail || detail;
      }} catch (err) {{
        // ignore
      }}
      throw new Error(detail);
    }}
    return response.json();
  }}

  async function loadCurrentUser() {{
    const me = await fetchJson('/api/admin/auth/me');
    currentUserId = me.id;
  }}

  function renderUsers(users) {{
    usersTable.innerHTML = users.map(user => `
      <tr>
        <td><input data-name="${{user.id}}" value="${{escapeHtml(user.name)}}" /></td>
        <td>${{escapeHtml(user.email)}}</td>
        <td>
          <select data-role="${{user.id}}">
            <option value="admin" ${{user.role === 'admin' ? 'selected' : ''}}>admin</option>
            <option value="operator" ${{user.role === 'operator' ? 'selected' : ''}}>operator</option>
            <option value="cashier" ${{user.role === 'cashier' ? 'selected' : ''}}>cashier</option>
          </select>
        </td>
        <td>
          <input type="checkbox" data-active="${{user.id}}" ${{user.active ? 'checked' : ''}} />
        </td>
        <td>${{user.id === currentUserId ? '<span class="pill">Você</span>' : ''}}</td>
        <td>
          <button class="btn" data-save="${{user.id}}">Salvar</button>
          <button class="btn secondary" data-reset="${{user.id}}">Reset senha</button>
        </td>
      </tr>
    `).join('');
  }}

  async function loadUsers() {{
    try {{
      listStatus.textContent = 'Carregando…';
      const users = await fetchJson(`/api/admin/users?tenant_id=${{TENANT_ID}}`);
      renderUsers(users);
      listStatus.textContent = users.length ? `${{users.length}} usuários` : 'Nenhum usuário cadastrado.';
    }} catch (err) {{
      listStatus.textContent = err.message || 'Erro ao carregar.';
    }}
  }}

  usersTable.addEventListener('click', async (event) => {{
    const target = event.target;
    if (target.dataset.save) {{
      const userId = target.dataset.save;
      const name = document.querySelector(`[data-name="${{userId}}"]`).value;
      const role = document.querySelector(`[data-role="${{userId}}"]`).value;
      const active = document.querySelector(`[data-active="${{userId}}"]`).checked;
      try {{
        await fetchJson(`/api/admin/users/${{userId}}`, {{
          method: 'PUT',
          body: JSON.stringify({{ name, role, active }}),
        }});
        await loadUsers();
      }} catch (err) {{
        alert(err.message || 'Erro ao salvar.');
      }}
    }}
    if (target.dataset.reset) {{
      const userId = target.dataset.reset;
      const password = prompt('Nova senha:');
      if (!password) return;
      try {{
        await fetchJson(`/api/admin/users/${{userId}}/reset_password`, {{
          method: 'POST',
          body: JSON.stringify({{ new_password: password }}),
        }});
        alert('Senha resetada com sucesso.');
      }} catch (err) {{
        alert(err.message || 'Erro ao resetar senha.');
      }}
    }}
  }});

  createForm.addEventListener('submit', async (event) => {{
    event.preventDefault();
    createStatus.textContent = 'Salvando…';
    const payload = {{
      tenant_id: TENANT_ID,
      name: document.getElementById('create-name').value.trim(),
      email: document.getElementById('create-email').value.trim(),
      role: document.getElementById('create-role').value,
      password: document.getElementById('create-password').value,
    }};
    try {{
      await fetchJson('/api/admin/users', {{
        method: 'POST',
        body: JSON.stringify(payload),
      }});
      createForm.reset();
      createStatus.textContent = 'Usuário criado.';
      await loadUsers();
    }} catch (err) {{
      createStatus.textContent = err.message || 'Erro ao criar.';
    }}
  }});

  async function init() {{
    await loadCurrentUser();
    await loadUsers();
  }}

  init();
</script>
</body>
</html>
"""
    return HTMLResponse(html)


@router.get("/admin/{tenant_id}/audit", response_class=HTMLResponse)
def admin_audit_page(
    tenant_id: int,
    _user: AdminUser = Depends(require_role_ui(["admin"])),
):
    html = f"""
<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Admin • Auditoria (Tenant {tenant_id})</title>
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
      background: radial-gradient(1100px 700px at 10% 0%, #18253a 0%, var(--bg) 60%);
      color: var(--text);
    }}
    header {{
      padding: 18px 22px;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
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
    .btn {{
      cursor: pointer;
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.04);
      color: var(--text);
      padding: 8px 12px;
      border-radius: 10px;
      transition: .15s ease;
      font-size: 12px;
    }}
    .btn:hover {{ background: rgba(255,255,255,0.08); }}
    main {{ padding: 18px; display: grid; gap: 16px; }}
    .card {{
      background: rgba(255,255,255,0.03);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
    }}
    .section {{ padding: 14px; border-bottom: 1px solid var(--border); }}
    .section:last-child {{ border-bottom: none; }}
    label {{ font-size: 12px; color: var(--muted); display: block; margin-bottom: 4px; }}
    input, select {{
      width: 100%;
      background: rgba(255,255,255,0.04);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 8px 10px;
      border-radius: 8px;
      font-size: 13px;
    }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{
      padding: 8px 10px;
      border-bottom: 1px solid var(--border);
      text-align: left;
    }}
    th {{ font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: .4px; }}
    .filters {{ display: grid; grid-template-columns: repeat(5, minmax(120px, 1fr)); gap: 10px; }}
    .status {{ font-size: 12px; color: var(--muted); }}
    @media (max-width: 980px) {{
      .filters {{ grid-template-columns: 1fr 1fr; }}
    }}
  </style>
</head>
<body>
<header>
  <div class="brand">
    <div class="logo"></div>
    <div class="title">
      <b>Auditoria</b>
      <span>Tenant {tenant_id} • logs administrativos</span>
    </div>
  </div>
  <div class="actions">
    <a class="btn" href="/admin/{tenant_id}/dashboard">Dashboard</a>
    <a class="btn" href="/admin/{tenant_id}/users">Usuários</a>
    <a class="btn" href="/admin/logout">Logout</a>
  </div>
</header>
<main>
  <div class="card">
    <div class="section">
      <h3>Filtros</h3>
      <div class="filters">
        <div>
          <label for="filter-from">De</label>
          <input type="date" id="filter-from" />
        </div>
        <div>
          <label for="filter-to">Até</label>
          <input type="date" id="filter-to" />
        </div>
        <div>
          <label for="filter-user">User ID</label>
          <input type="number" id="filter-user" min="1" />
        </div>
        <div>
          <label for="filter-action">Ação</label>
          <input id="filter-action" placeholder="login_failed..." />
        </div>
        <div style="align-self:end;">
          <button class="btn" id="apply-filters">Aplicar filtros</button>
        </div>
      </div>
      <div class="status" id="audit-status">Carregando…</div>
    </div>
    <div class="section">
      <table>
        <thead>
          <tr>
            <th>Data</th>
            <th>Usuário</th>
            <th>Ação</th>
            <th>Entidade</th>
            <th>Meta</th>
          </tr>
        </thead>
        <tbody id="audit-table"></tbody>
      </table>
    </div>
  </div>
</main>
<script>
  const TENANT_ID = {tenant_id};
  const auditStatus = document.getElementById('audit-status');
  const auditTable = document.getElementById('audit-table');
  const applyButton = document.getElementById('apply-filters');

  function escapeHtml(value) {{
    return (value || '').replace(/[&<>\"']/g, (char) => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;',
    }}[char]));
  }}

  async function fetchJson(url) {{
    const response = await fetch(url, {{
      credentials: 'same-origin',
    }});
    if (!response.ok) {{
      throw new Error('Erro ao carregar auditoria.');
    }}
    return response.json();
  }}

  function buildQuery() {{
    const params = new URLSearchParams();
    params.set('tenant_id', TENANT_ID);
    const from = document.getElementById('filter-from').value;
    const to = document.getElementById('filter-to').value;
    const userId = document.getElementById('filter-user').value;
    const action = document.getElementById('filter-action').value;
    if (from) params.set('from', from);
    if (to) params.set('to', to);
    if (userId) params.set('user_id', userId);
    if (action) params.set('action', action);
    return params.toString();
  }}

  function renderRows(rows) {{
    auditTable.innerHTML = rows.map(row => {{
      const meta = row.meta ? JSON.stringify(row.meta) : '';
      const userLabel = row.user_name ? `${{row.user_name}} (${{row.user_email || row.user_id}})` : `#${{row.user_id}}`;
      const entity = row.entity_type ? `${{row.entity_type}} #${{row.entity_id || ''}}` : '';
      return `
        <tr>
          <td>${{escapeHtml(new Date(row.created_at).toLocaleString())}}</td>
          <td>${{escapeHtml(userLabel)}}</td>
          <td>${{escapeHtml(row.action)}}</td>
          <td>${{escapeHtml(entity)}}</td>
          <td>${{escapeHtml(meta)}}</td>
        </tr>
      `;
    }}).join('');
  }}

  async function loadAudit() {{
    auditStatus.textContent = 'Carregando…';
    try {{
      const rows = await fetchJson(`/api/admin/audit?${{buildQuery()}}`);
      renderRows(rows);
      auditStatus.textContent = rows.length ? `${{rows.length}} registros` : 'Nenhum registro encontrado.';
    }} catch (err) {{
      auditStatus.textContent = err.message || 'Erro ao carregar.';
    }}
  }}

  applyButton.addEventListener('click', loadAudit);
  loadAudit();
</script>
</body>
</html>
"""
    return HTMLResponse(html)


@router.get("/admin/{tenant_id}/inventory/movements", response_class=HTMLResponse)
def admin_inventory_movements(
    tenant_id: int,
    _user: AdminUser = Depends(require_role_ui(["admin"])),
):
    html = """
<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Painel do Dono • Movimentos de estoque (Tenant __TENANT_ID__)</title>
  <style>
    :root {
      --bg: #0b0f14;
      --card: #121826;
      --muted: #91a4b7;
      --text: #e7eef6;
      --border: rgba(255,255,255,0.08);
      --shadow: 0 10px 30px rgba(0,0,0,.35);
      --radius: 14px;
      --accent: #63e6be;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial;
      background: radial-gradient(1000px 700px at 10% 0%, #142136 0%, var(--bg) 60%);
      color: var(--text);
    }
    header {
      padding: 18px 22px;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }
    .brand { display: flex; align-items: center; gap: 10px; }
    .logo {
      width: 34px; height: 34px;
      border-radius: 10px;
      background: linear-gradient(135deg, #63e6be, #3bc9db);
      box-shadow: var(--shadow);
    }
    .title { display: flex; flex-direction: column; line-height: 1.1; }
    .title b { font-size: 16px; }
    .title span { font-size: 12px; color: var(--muted); }
    .pill {
      padding: 8px 10px;
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.03);
      border-radius: 999px;
      color: var(--muted);
      font-size: 12px;
    }
    .btn {
      cursor: pointer;
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.04);
      color: var(--text);
      padding: 9px 12px;
      border-radius: 10px;
      transition: .15s ease;
      font-size: 12px;
    }
    .btn:hover { background: rgba(255,255,255,0.08); }
    main { padding: 18px; }
    .layout { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
    .card {
      background: rgba(255,255,255,0.03);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
    }
    .section { padding: 14px; border-bottom: 1px solid var(--border); }
    .section:last-child { border-bottom: none; }
    .section h3 { margin: 0 0 10px; font-size: 14px; letter-spacing: .3px; }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }
    th, td {
      padding: 8px 10px;
      text-align: left;
      border-bottom: 1px solid var(--border);
    }
    th { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .4px; }
    label { font-size: 12px; color: var(--muted); display: block; margin-bottom: 4px; }
    input, select {
      width: 100%;
      background: rgba(255,255,255,0.04);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 8px 10px;
      border-radius: 8px;
      font-size: 13px;
    }
    .form-grid { display: grid; gap: 10px; }
    .actions { display: flex; gap: 8px; flex-wrap: wrap; }
    .muted { color: var(--muted); font-size: 12px; }
    @media (max-width: 980px) {
      .layout { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
<header>
  <div class="brand">
    <div class="logo"></div>
    <div class="title">
      <b>Movimentos de estoque</b>
      <span>Tenant __TENANT_ID__ • Entradas e saídas</span>
    </div>
  </div>
  <div class="actions">
    <span class="pill" id="status">Carregando…</span>
    <a class="btn" href="/admin/__TENANT_ID__/reports">Relatórios</a>
    <a class="btn" href="/admin/__TENANT_ID__/inventory/items">Itens</a>
    <a class="btn" href="/admin/__TENANT_ID__/inventory/recipes">Receitas</a>
    <a class="btn" href="/admin/__TENANT_ID__/users">Usuários</a>
    <a class="btn" href="/admin/__TENANT_ID__/audit">Auditoria</a>
    <a class="btn" href="/admin/logout">Logout</a>
  </div>
</header>
<main>
  <div class="layout">
    <div class="card">
      <div class="section">
        <h3>Registrar movimento</h3>
        <form class="form-grid" onsubmit="event.preventDefault(); saveMovement();">
          <div>
            <label for="item">Item</label>
            <select id="item"></select>
          </div>
          <div>
            <label for="type">Tipo</label>
            <select id="type">
              <option value="IN">Entrada</option>
              <option value="OUT">Saída</option>
              <option value="ADJUST">Ajuste (saldo)</option>
            </select>
          </div>
          <div>
            <label for="quantity">Quantidade</label>
            <input id="quantity" type="number" min="0.01" step="0.01" required />
          </div>
          <div>
            <label for="reason">Motivo</label>
            <input id="reason" placeholder="Compra, perda, ajuste..." />
          </div>
          <div class="actions">
            <button class="btn" type="submit">Registrar</button>
          </div>
        </form>
        <div class="muted" id="form-status"></div>
      </div>
    </div>
    <div class="card">
      <div class="section">
        <h3>Movimentos recentes</h3>
        <table>
          <thead>
            <tr>
              <th>Item</th>
              <th>Tipo</th>
              <th>Qtd</th>
              <th>Motivo</th>
              <th>Pedido</th>
              <th>Data</th>
            </tr>
          </thead>
          <tbody id="movements-table"></tbody>
        </table>
      </div>
    </div>
  </div>
</main>
<script>
  const TENANT_ID = Number('__TENANT_ID__');
  const statusEl = document.getElementById('status');
  const itemSelect = document.getElementById('item');
  const typeSelect = document.getElementById('type');
  const quantityInput = document.getElementById('quantity');
  const reasonInput = document.getElementById('reason');
  const formStatusEl = document.getElementById('form-status');
  const movementsTableEl = document.getElementById('movements-table');

  async function fetchJson(url, options) {
    const response = await fetch(url, options);
    if (!response.ok) {
      let detail = 'Erro ao carregar dados.';
      try {
        const data = await response.json();
        if (data && data.detail) detail = data.detail;
      } catch (err) {
        // ignore
      }
      throw new Error(detail);
    }
    return response.json();
  }

  function setStatus(message) {
    statusEl.textContent = message;
  }

  function formatDate(value) {
    if (!value) return '-';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString('pt-BR');
  }

  async function loadItems() {
    const items = await fetchJson(`/api/inventory/items?tenant_id=${TENANT_ID}`);
    itemSelect.innerHTML = '';
    items.forEach((item) => {
      const option = document.createElement('option');
      option.value = item.id;
      option.textContent = `${item.name} (${item.unit})`;
      itemSelect.appendChild(option);
    });
  }

  async function loadMovements() {
    const movements = await fetchJson(`/api/inventory/movements?tenant_id=${TENANT_ID}`);
    movementsTableEl.innerHTML = '';
    if (!movements.length) {
      movementsTableEl.innerHTML = '<tr><td colspan="6" class="muted">Nenhum movimento registrado.</td></tr>';
      return;
    }
    movements.forEach((movement) => {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td>${movement.item_name}</td>
        <td>${movement.type}</td>
        <td>${movement.quantity}</td>
        <td>${movement.reason || '-'}</td>
        <td>${movement.order_id ? `#${movement.order_id}` : '-'}</td>
        <td>${formatDate(movement.created_at)}</td>
      `;
      movementsTableEl.appendChild(row);
    });
  }

  async function saveMovement() {
    try {
      formStatusEl.textContent = '';
      const payload = {
        inventory_item_id: Number(itemSelect.value),
        type: typeSelect.value,
        quantity: Number(quantityInput.value || 0),
        reason: reasonInput.value.trim() || null,
      };
      if (!payload.inventory_item_id) {
        throw new Error('Selecione um item.');
      }
      if (!payload.quantity || payload.quantity <= 0) {
        throw new Error('Quantidade inválida.');
      }
      await fetchJson(`/api/inventory/movements?tenant_id=${TENANT_ID}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      quantityInput.value = '';
      reasonInput.value = '';
      await loadMovements();
      formStatusEl.textContent = 'Movimento registrado.';
    } catch (err) {
      formStatusEl.textContent = err.message || 'Erro ao salvar.';
    }
  }

  async function init() {
    try {
      setStatus('Carregando dados…');
      await loadItems();
      await loadMovements();
      setStatus('Pronto');
    } catch (err) {
      setStatus(err.message || 'Erro ao carregar.');
    }
  }

  init();
</script>
</body>
</html>
"""
    return HTMLResponse(html.replace("__TENANT_ID__", str(tenant_id)))


@router.get("/admin/{tenant_id}/inventory/recipes", response_class=HTMLResponse)
def admin_inventory_recipes(
    tenant_id: int,
    _user: AdminUser = Depends(require_role_ui(["admin"])),
):
    html = """
<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Painel do Dono • Receitas (Tenant __TENANT_ID__)</title>
  <style>
    :root {
      --bg: #0b0f14;
      --card: #121826;
      --muted: #91a4b7;
      --text: #e7eef6;
      --border: rgba(255,255,255,0.08);
      --shadow: 0 10px 30px rgba(0,0,0,.35);
      --radius: 14px;
      --accent: #ffb86b;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial;
      background: radial-gradient(1000px 700px at 10% 0%, #142136 0%, var(--bg) 60%);
      color: var(--text);
    }
    header {
      padding: 18px 22px;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }
    .brand { display: flex; align-items: center; gap: 10px; }
    .logo {
      width: 34px; height: 34px;
      border-radius: 10px;
      background: linear-gradient(135deg, #ffb86b, #ff4d6d);
      box-shadow: var(--shadow);
    }
    .title { display: flex; flex-direction: column; line-height: 1.1; }
    .title b { font-size: 16px; }
    .title span { font-size: 12px; color: var(--muted); }
    .pill {
      padding: 8px 10px;
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.03);
      border-radius: 999px;
      color: var(--muted);
      font-size: 12px;
    }
    .btn {
      cursor: pointer;
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.04);
      color: var(--text);
      padding: 9px 12px;
      border-radius: 10px;
      transition: .15s ease;
      font-size: 12px;
    }
    .btn:hover { background: rgba(255,255,255,0.08); }
    main { padding: 18px; }
    .layout { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
    .card {
      background: rgba(255,255,255,0.03);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
    }
    .section { padding: 14px; border-bottom: 1px solid var(--border); }
    .section:last-child { border-bottom: none; }
    .section h3 { margin: 0 0 10px; font-size: 14px; letter-spacing: .3px; }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }
    th, td {
      padding: 8px 10px;
      text-align: left;
      border-bottom: 1px solid var(--border);
    }
    th { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .4px; }
    label { font-size: 12px; color: var(--muted); display: block; margin-bottom: 4px; }
    input, select {
      width: 100%;
      background: rgba(255,255,255,0.04);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 8px 10px;
      border-radius: 8px;
      font-size: 13px;
    }
    .form-grid { display: grid; gap: 10px; }
    .actions { display: flex; gap: 8px; flex-wrap: wrap; }
    .muted { color: var(--muted); font-size: 12px; }
    @media (max-width: 980px) {
      .layout { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
<header>
  <div class="brand">
    <div class="logo"></div>
    <div class="title">
      <b>Receitas</b>
      <span>Tenant __TENANT_ID__ • Insumos por item</span>
    </div>
  </div>
  <div class="actions">
    <span class="pill" id="status">Carregando…</span>
    <a class="btn" href="/admin/__TENANT_ID__/reports">Relatórios</a>
    <a class="btn" href="/admin/__TENANT_ID__/inventory/items">Itens</a>
    <a class="btn" href="/admin/__TENANT_ID__/inventory/movements">Movimentos</a>
    <a class="btn" href="/admin/__TENANT_ID__/users">Usuários</a>
    <a class="btn" href="/admin/__TENANT_ID__/audit">Auditoria</a>
    <a class="btn" href="/admin/logout">Logout</a>
  </div>
</header>
<main>
  <div class="layout">
    <div class="card">
      <div class="section">
        <h3>Ingredientes por item do cardápio</h3>
        <form class="form-grid" onsubmit="event.preventDefault(); addMenuIngredient();">
          <div>
            <label for="menu-item">Item do cardápio</label>
            <select id="menu-item"></select>
          </div>
          <div>
            <label for="menu-ingredient">Insumo</label>
            <select id="menu-ingredient"></select>
          </div>
          <div>
            <label for="menu-qty">Quantidade</label>
            <input id="menu-qty" type="number" min="0.01" step="0.01" required />
          </div>
          <div class="actions">
            <button class="btn" type="submit">Adicionar</button>
          </div>
        </form>
        <div class="muted" id="menu-status"></div>
      </div>
      <div class="section">
        <table>
          <thead>
            <tr>
              <th>Insumo</th>
              <th>Qtd</th>
              <th></th>
            </tr>
          </thead>
          <tbody id="menu-ingredients-table"></tbody>
        </table>
      </div>
    </div>
    <div class="card">
      <div class="section">
        <h3>Ingredientes por adicional</h3>
        <form class="form-grid" onsubmit="event.preventDefault(); addModifierIngredient();">
          <div>
            <label for="modifier">Adicional</label>
            <select id="modifier"></select>
          </div>
          <div>
            <label for="modifier-ingredient">Insumo</label>
            <select id="modifier-ingredient"></select>
          </div>
          <div>
            <label for="modifier-qty">Quantidade</label>
            <input id="modifier-qty" type="number" min="0.01" step="0.01" required />
          </div>
          <div class="actions">
            <button class="btn" type="submit">Adicionar</button>
          </div>
        </form>
        <div class="muted" id="modifier-status"></div>
      </div>
      <div class="section">
        <table>
          <thead>
            <tr>
              <th>Insumo</th>
              <th>Qtd</th>
              <th></th>
            </tr>
          </thead>
          <tbody id="modifier-ingredients-table"></tbody>
        </table>
      </div>
    </div>
  </div>
</main>
<script>
  const TENANT_ID = Number('__TENANT_ID__');
  const statusEl = document.getElementById('status');
  const menuItemSelect = document.getElementById('menu-item');
  const menuIngredientSelect = document.getElementById('menu-ingredient');
  const menuQtyInput = document.getElementById('menu-qty');
  const menuStatusEl = document.getElementById('menu-status');
  const menuTableEl = document.getElementById('menu-ingredients-table');
  const modifierSelect = document.getElementById('modifier');
  const modifierIngredientSelect = document.getElementById('modifier-ingredient');
  const modifierQtyInput = document.getElementById('modifier-qty');
  const modifierStatusEl = document.getElementById('modifier-status');
  const modifierTableEl = document.getElementById('modifier-ingredients-table');

  async function fetchJson(url, options) {
    const response = await fetch(url, options);
    if (!response.ok) {
      let detail = 'Erro ao carregar dados.';
      try {
        const data = await response.json();
        if (data && data.detail) detail = data.detail;
      } catch (err) {
        // ignore
      }
      throw new Error(detail);
    }
    return response.json();
  }

  function setStatus(message) {
    statusEl.textContent = message;
  }

  function fillSelect(select, items, labelFn) {
    select.innerHTML = '';
    items.forEach((item) => {
      const option = document.createElement('option');
      option.value = item.id;
      option.textContent = labelFn(item);
      select.appendChild(option);
    });
  }

  async function loadInventoryItems() {
    const items = await fetchJson(`/api/inventory/items?tenant_id=${TENANT_ID}`);
    fillSelect(menuIngredientSelect, items, (item) => `${item.name} (${item.unit})`);
    fillSelect(modifierIngredientSelect, items, (item) => `${item.name} (${item.unit})`);
  }

  async function loadMenuItems() {
    const items = await fetchJson(`/api/menu?tenant_id=${TENANT_ID}`);
    fillSelect(menuItemSelect, items, (item) => item.name);
  }

  async function loadModifiers() {
    const groups = await fetchJson(`/api/modifiers/groups/${TENANT_ID}`);
    const allModifiers = [];
    for (const group of groups) {
      const mods = await fetchJson(`/api/modifiers/groups/${TENANT_ID}/${group.id}/modifiers`);
      mods.forEach((mod) => allModifiers.push(mod));
    }
    fillSelect(modifierSelect, allModifiers, (mod) => mod.name);
  }

  async function loadMenuIngredients() {
    if (!menuItemSelect.value) return;
    const ingredients = await fetchJson(`/api/inventory/menu-items/${menuItemSelect.value}/ingredients?tenant_id=${TENANT_ID}`);
    menuTableEl.innerHTML = '';
    if (!ingredients.length) {
      menuTableEl.innerHTML = '<tr><td colspan="3" class="muted">Nenhum ingrediente.</td></tr>';
      return;
    }
    ingredients.forEach((ingredient) => {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td>${ingredient.name}</td>
        <td>${ingredient.quantity} ${ingredient.unit}</td>
        <td><button class="btn" data-id="${ingredient.id}">Excluir</button></td>
      `;
      row.querySelector('button').addEventListener('click', () => deleteMenuIngredient(ingredient.id));
      menuTableEl.appendChild(row);
    });
  }

  async function loadModifierIngredients() {
    if (!modifierSelect.value) return;
    const ingredients = await fetchJson(`/api/inventory/modifiers/${modifierSelect.value}/ingredients?tenant_id=${TENANT_ID}`);
    modifierTableEl.innerHTML = '';
    if (!ingredients.length) {
      modifierTableEl.innerHTML = '<tr><td colspan="3" class="muted">Nenhum ingrediente.</td></tr>';
      return;
    }
    ingredients.forEach((ingredient) => {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td>${ingredient.name}</td>
        <td>${ingredient.quantity} ${ingredient.unit}</td>
        <td><button class="btn" data-id="${ingredient.id}">Excluir</button></td>
      `;
      row.querySelector('button').addEventListener('click', () => deleteModifierIngredient(ingredient.id));
      modifierTableEl.appendChild(row);
    });
  }

  async function addMenuIngredient() {
    try {
      menuStatusEl.textContent = '';
      const payload = {
        inventory_item_id: Number(menuIngredientSelect.value),
        quantity: Number(menuQtyInput.value || 0),
      };
      if (!payload.inventory_item_id) throw new Error('Selecione um insumo.');
      if (!payload.quantity || payload.quantity <= 0) throw new Error('Quantidade inválida.');
      await fetchJson(`/api/inventory/menu-items/${menuItemSelect.value}/ingredients?tenant_id=${TENANT_ID}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      menuQtyInput.value = '';
      await loadMenuIngredients();
      menuStatusEl.textContent = 'Ingrediente salvo.';
    } catch (err) {
      menuStatusEl.textContent = err.message || 'Erro ao salvar.';
    }
  }

  async function deleteMenuIngredient(ingredientId) {
    await fetchJson(`/api/inventory/menu-items/${menuItemSelect.value}/ingredients?tenant_id=${TENANT_ID}&ingredient_id=${ingredientId}`, {
      method: 'DELETE',
    });
    await loadMenuIngredients();
  }

  async function addModifierIngredient() {
    try {
      modifierStatusEl.textContent = '';
      const payload = {
        inventory_item_id: Number(modifierIngredientSelect.value),
        quantity: Number(modifierQtyInput.value || 0),
      };
      if (!payload.inventory_item_id) throw new Error('Selecione um insumo.');
      if (!payload.quantity || payload.quantity <= 0) throw new Error('Quantidade inválida.');
      await fetchJson(`/api/inventory/modifiers/${modifierSelect.value}/ingredients?tenant_id=${TENANT_ID}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      modifierQtyInput.value = '';
      await loadModifierIngredients();
      modifierStatusEl.textContent = 'Ingrediente salvo.';
    } catch (err) {
      modifierStatusEl.textContent = err.message || 'Erro ao salvar.';
    }
  }

  async function deleteModifierIngredient(ingredientId) {
    await fetchJson(`/api/inventory/modifiers/${modifierSelect.value}/ingredients?tenant_id=${TENANT_ID}&ingredient_id=${ingredientId}`, {
      method: 'DELETE',
    });
    await loadModifierIngredients();
  }

  menuItemSelect.addEventListener('change', loadMenuIngredients);
  modifierSelect.addEventListener('change', loadModifierIngredients);

  async function init() {
    try {
      setStatus('Carregando dados…');
      await Promise.all([loadInventoryItems(), loadMenuItems(), loadModifiers()]);
      await loadMenuIngredients();
      await loadModifierIngredients();
      setStatus('Pronto');
    } catch (err) {
      setStatus(err.message || 'Erro ao carregar.');
    }
  }

  init();
</script>
</body>
</html>
"""
    return HTMLResponse(html.replace("__TENANT_ID__", str(tenant_id)))
