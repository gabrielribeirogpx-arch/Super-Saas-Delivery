from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.services.printing import get_print_settings, save_print_settings, list_printers_windows


router = APIRouter()


class PrintSettingsIn(BaseModel):
    auto_print: bool = False
    mode: str = "pdf"  # pdf | print
    printer_name: str | None = None


@router.get("/api/settings/{tenant_id}/printing")
def get_printing_settings(tenant_id: int):
    return get_print_settings(tenant_id)


@router.get("/api/settings/{tenant_id}/printers")
def get_printers(tenant_id: int):
    require_tenant_access(tenant_id, current_user)
    # tenant_id não é usado, mas mantemos no path para consistência multi-tenant
    if list_printers_windows is None:
        return {"printers": []}
    if __import__("os").name != "nt":
        return {"printers": []}
    return {"printers": list_printers_windows()}


@router.put("/api/settings/{tenant_id}/printing")
def update_printing_settings(tenant_id: int, body: PrintSettingsIn):
    # normaliza
    mode = (body.mode or "pdf").lower()
    if mode not in ("pdf", "print"):
        raise HTTPException(status_code=400, detail="mode deve ser 'pdf' ou 'print'")
    return save_print_settings(
        tenant_id,
        {
            "auto_print": body.auto_print,
            "mode": mode,
            "printer_name": body.printer_name,
        },
    )


@router.get("/painel/{tenant_id}/config", response_class=HTMLResponse)
def config_page(tenant_id: int):
    # Página simples (sem frameworks) para o dono do restaurante configurar sem mexer em .env
    html = f"""<!doctype html>
<html lang="pt-br">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Configurações - Tenant {tenant_id}</title>
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial; background:#0b1220; color:#e5e7eb; margin:0; }}
    .wrap {{ max-width: 880px; margin: 32px auto; padding: 0 16px; }}
    .card {{ background:#0f172a; border:1px solid rgba(255,255,255,.08); border-radius:16px; padding:18px; box-shadow: 0 10px 30px rgba(0,0,0,.25); }}
    h1 {{ font-size: 20px; margin:0 0 8px; }}
    p {{ margin: 0 0 16px; color:#cbd5e1; }}
    label {{ display:block; margin: 12px 0 6px; color:#cbd5e1; }}
    input[type="checkbox"] {{ transform: scale(1.2); margin-right: 8px; }}
    select, button {{ width: 100%; padding: 10px 12px; border-radius: 10px; border:1px solid rgba(255,255,255,.12); background:#0b1020; color:#e5e7eb; }}
    button {{ margin-top: 12px; background:#1d4ed8; border:none; cursor:pointer; }}
    button:hover {{ filter: brightness(1.1); }}
    .row {{ display:grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
    .hint {{ font-size: 12px; color:#94a3b8; margin-top: 6px; }}
    .ok {{ color:#86efac; font-size: 13px; margin-top: 10px; display:none; }}
    .err {{ color:#fca5a5; font-size: 13px; margin-top: 10px; display:none; }}
    @media (max-width: 700px) {{ .row {{ grid-template-columns: 1fr; }} }}
    a {{ color:#93c5fd; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>Configurações do Restaurante</h1>
      <p>Tenant <b>{tenant_id}</b>. Aqui você escolhe se o sistema vai tentar imprimir automaticamente quando chegar um pedido.</p>

      <label>
        <input id="auto_print" type="checkbox" />
        Imprimir automaticamente quando o pedido chegar na cozinha
      </label>
      <div class="hint">Se não houver impressora, o sistema continua gerando o PDF do ticket.</div>

      <div class="row">
        <div>
          <label for="mode">Modo</label>
          <select id="mode">
            <option value="pdf">Gerar PDF (recomendado)</option>
            <option value="print">Imprimir (Windows + impressora padrão)</option>
          </select>
          <div class="hint">No modo <b>Imprimir</b>, o Windows imprime na impressora padrão.</div>
        </div>
        <div>
          <label for="printer_name">Impressora preferida (opcional)</label>
          <select id="printer_name">
            <option value="">(usar padrão do Windows)</option>
          </select>
          <div class="hint">Vamos usar essa info para validar se existe e evoluir para seleção direta.</div>
        </div>
      </div>

      <button id="save">Salvar</button>
      <div class="ok" id="ok">Salvo ✅</div>
      <div class="err" id="err">Erro ao salvar.</div>

      <p class="hint" style="margin-top:16px;">Voltar: <a href="/painel/{tenant_id}">KDS</a></p>
    </div>
  </div>

<script>
async function load() {{
  const sRes = await fetch(`/api/settings/{tenant_id}/printing`);
  const s = await sRes.json();
  document.getElementById('auto_print').checked = !!s.auto_print;
  document.getElementById('mode').value = (s.mode || 'pdf');

  // printers
  try {{
    const pRes = await fetch(`/api/settings/{tenant_id}/printers`);
    const p = await pRes.json();
    const sel = document.getElementById('printer_name');
    (p.printers || []).forEach(name => {{
      const opt = document.createElement('option');
      opt.value = name; opt.textContent = name;
      sel.appendChild(opt);
    }});
    sel.value = s.printer_name || '';
  }} catch (e) {{
    // ignore
  }}
}}

async function save() {{
  document.getElementById('ok').style.display = 'none';
  document.getElementById('err').style.display = 'none';

  const payload = {{
    auto_print: document.getElementById('auto_print').checked,
    mode: document.getElementById('mode').value,
    printer_name: document.getElementById('printer_name').value || null,
  }};
  const res = await fetch(`/api/settings/{tenant_id}/printing`, {{
    method:'PUT',
    headers: {{'Content-Type':'application/json'}},
    body: JSON.stringify(payload)
  }});
  if (res.ok) {{
    document.getElementById('ok').style.display = 'block';
  }} else {{
    document.getElementById('err').style.display = 'block';
  }}
}}

document.getElementById('save').addEventListener('click', save);
load();
</script>
</body>
</html>"""
    return HTMLResponse(html)
