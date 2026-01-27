from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["delivery"])


@router.get("/entregador/{tenant_id}", response_class=HTMLResponse)
def delivery_panel(tenant_id: int):
    html = f"""
<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Painel do Entregador (Tenant {tenant_id})</title>
  <style>
    :root {{
      --bg: #0b0f14;
      --card: #121826;
      --muted: #91a4b7;
      --text: #e7eef6;
      --border: rgba(255,255,255,0.08);
      --shadow: 0 10px 30px rgba(0,0,0,.35);
      --radius: 14px;
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
    .brand {{
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .logo {{
      width: 34px; height: 34px;
      border-radius: 10px;
      background: linear-gradient(135deg, #63e6be, #4dabf7);
      box-shadow: var(--shadow);
    }}
    .title {{
      display: flex;
      flex-direction: column;
      line-height: 1.1;
    }}
    .title b {{ font-size: 16px; }}
    .title span {{ font-size: 12px; color: var(--muted); }}
    .controls {{
      display: flex;
      align-items: center;
      gap: 10px;
    }}
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
    main {{
      padding: 18px 18px 26px;
    }}
    .board {{
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 14px;
    }}
    .col {{
      background: rgba(255,255,255,0.03);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      overflow: hidden;
      min-height: 72vh;
      box-shadow: var(--shadow);
    }}
    .colheader {{
      padding: 12px 14px;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      position: sticky;
      top: 0;
      background: rgba(10,14,20,0.75);
      backdrop-filter: blur(8px);
    }}
    .colheader b {{ font-size: 13px; letter-spacing: .3px; }}
    .count {{
      font-size: 12px;
      color: var(--muted);
      border: 1px solid var(--border);
      padding: 4px 8px;
      border-radius: 999px;
    }}
    .list {{
      padding: 12px;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}
    .card {{
      border: 1px solid var(--border);
      background: linear-gradient(180deg, rgba(255,255,255,0.05), rgba(255,255,255,0.03));
      border-radius: 14px;
      padding: 12px;
      box-shadow: 0 8px 18px rgba(0,0,0,.25);
    }}
    .toprow {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 10px;
    }}
    .badge {{
      font-size: 11px;
      color: #0b0f14;
      background: #63e6be;
      padding: 4px 8px;
      border-radius: 999px;
      font-weight: 700;
    }}
    .meta {{
      font-size: 12px;
      color: var(--muted);
    }}
    .client {{
      margin-top: 6px;
      font-size: 12px;
      color: var(--muted);
    }}
    .items {{
      margin-top: 10px;
      font-size: 13px;
      line-height: 1.35;
      white-space: pre-wrap;
    }}
    .row {{
      margin-top: 10px;
      display: grid;
      gap: 6px;
      font-size: 12px;
      color: var(--muted);
    }}
    .obs {{
      margin-top: 10px;
      padding: 9px 10px;
      border-radius: 12px;
      border: 1px solid rgba(255,77,109,0.25);
      background: rgba(255,77,109,0.12);
      color: #ffd3db;
      font-size: 12px;
      font-weight: 600;
    }}
    .actions {{
      margin-top: 12px;
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .action {{
      cursor: pointer;
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.04);
      color: var(--text);
      padding: 8px 10px;
      border-radius: 10px;
      font-size: 12px;
    }}
    .action.primary {{ background: rgba(77,171,247,0.18); border-color: rgba(77,171,247,0.35); }}
    .action.good {{ background: rgba(56,219,140,0.12); border-color: rgba(56,219,140,0.25); }}
    .footer {{
      margin-top: 12px;
      font-size: 11px;
      color: var(--muted);
      display: flex;
      justify-content: space-between;
      gap: 10px;
    }}
    @media (max-width: 980px) {{
      .board {{ grid-template-columns: 1fr; }}
      .col {{ min-height: auto; }}
    }}
  </style>
</head>
<body>
<header>
  <div class="brand">
    <div class="logo"></div>
    <div class="title">
      <b>Painel do Entregador</b>
      <span>Tenant {tenant_id} • Atualiza automaticamente</span>
    </div>
  </div>
  <div class="controls">
    <div class="pill" id="pill">Sincronizando…</div>
    <button class="btn" onclick="loadOrders(true)">Atualizar agora</button>
  </div>
</header>

<main>
  <div class="board">
    <section class="col">
      <div class="colheader">
        <b>Pronto para entrega</b>
        <span class="count" id="c_pronto">0</span>
      </div>
      <div class="list" id="pronto"></div>
    </section>
    <section class="col">
      <div class="colheader">
        <b>Saiu para entrega</b>
        <span class="count" id="c_saiu">0</span>
      </div>
      <div class="list" id="saiu"></div>
    </section>
  </div>
</main>

<script>
const TENANT_ID = {tenant_id};

function fmtTime(iso) {{
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleTimeString("pt-BR", {{hour: "2-digit", minute: "2-digit"}});
}}

function safe(t) {{
  return (t || "").toString();
}}

function normalizeStatus(status) {{
  const s = safe(status).toUpperCase();
  if (s === "SAIU") return "SAIU_PARA_ENTREGA";
  return s;
}}

function cardHtml(o) {{
  const entrega = safe(o.tipo_entrega).toUpperCase();
  const pag = safe(o.forma_pagamento).toUpperCase();
  const phone = safe(o.cliente_telefone);
  const nome = safe(o.cliente_nome);
  const when = fmtTime(o.created_at);
  const status = normalizeStatus(o.status);

  const obs = safe(o.observacao).trim();
  const showObs = obs && obs.toLowerCase() !== "sem observações" && obs.toLowerCase() !== "sem observacoes";

  const badge = entrega === "RETIRADA" ? "RETIRADA" : "ENTREGA";

  return `
  <div class="card" data-id="${{o.id}}">
    <div class="toprow">
      <div class="meta"><b>#${{o.id}}</b> • ${{when}} • <b>${{nome || "Cliente"}}</b></div>
      <div class="badge">${{badge}}</div>
    </div>

    <div class="client"><b>Cliente:</b> ${{nome || "Cliente WhatsApp"}} • <b>Tel:</b> ${{phone}}</div>

    <div class="items"><b>Itens:</b> ${{safe(o.itens)}}</div>

    <div class="row">
      <div><b>Pagamento:</b> ${{pag || "-"}}</div>
      <div><b>Endereço:</b> ${{safe(o.endereco) || "-"}}</div>
    </div>

    ${{showObs ? `<div class="obs">⚠ Observação: ${{obs}}</div>` : ""}}

    <div class="actions">
      ${{status === "PRONTO" ? `<button class="action primary" onclick="setStatus(${{o.id}}, 'SAIU_PARA_ENTREGA')">🛵 Saiu para entrega</button>` : ""}}
      ${{status === "SAIU_PARA_ENTREGA" ? `<button class="action good" onclick="setStatus(${{o.id}}, 'ENTREGUE')">📦 Entregue</button>` : ""}}
    </div>

    <div class="footer">
      <span>Status: <b>${{safe(o.status)}}</b></span>
      <span>${{o.valor_total ? ("R$ " + (o.valor_total/100).toFixed(2).replace(".", ",")) : ""}}</span>
    </div>
  </div>`;
}}

function setPill(msg) {{
  const pill = document.getElementById("pill");
  pill.textContent = msg;
}}

async function setStatus(id, status) {{
  try {{
    const r = await fetch(`/api/orders/${{id}}/status`, {{
      method: "PATCH",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify({{ status }})
    }});
    if (!r.ok) {{
      const t = await r.text();
      alert("Erro ao mudar status: " + t);
      return;
    }}
    await loadOrders(true);
  }} catch(e) {{
    alert("Falha na rede ao mudar status.");
  }}
}}

async function loadOrders() {{
  try {{
    const r = await fetch(`/api/orders/${{TENANT_ID}}/delivery?status=PRONTO,SAIU_PARA_ENTREGA`);
    if (!r.ok) {{
      setPill("Erro ao buscar pedidos");
      return;
    }}
    const orders = await r.json();

    const pronto = orders.filter(o => normalizeStatus(o.status) === "PRONTO");
    const saiu = orders.filter(o => normalizeStatus(o.status) === "SAIU_PARA_ENTREGA");

    document.getElementById("pronto").innerHTML = pronto.map(cardHtml).join("");
    document.getElementById("saiu").innerHTML = saiu.map(cardHtml).join("");

    document.getElementById("c_pronto").textContent = pronto.length;
    document.getElementById("c_saiu").textContent = saiu.length;

    setPill("Online • Atualizado");
  }} catch(e) {{
    setPill("Sem conexão • tentando…");
  }}
}}

loadOrders();
setInterval(loadOrders, 3000);
</script>
</body>
</html>
"""
    return HTMLResponse(html)
