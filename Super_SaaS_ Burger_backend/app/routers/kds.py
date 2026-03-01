from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.production import normalize_production_area
from app.deps import get_request_tenant_id, get_current_admin_user_ui, require_admin_tenant_access, require_admin_user
from app.models.admin_user import AdminUser
from app.models.menu_item import MenuItem
from app.models.modifier_group import ModifierGroup
from app.models.modifier_option import ModifierOption
from app.models.order import Order
from app.models.order_item import OrderItem
from app.services.admin_audit import log_admin_action
from app.services.order_events import emit_order_status_changed

router = APIRouter(tags=["kds"])

ACTIVE_STATUSES = {"pending", "preparing"}

def _normalize_area(area: str) -> str:
    try:
        return normalize_production_area(area)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _parse_ready_areas(value: str | None) -> List[str]:
    if not value:
        return []
    try:
        data = json.loads(value)
        if isinstance(data, list):
            return [str(item).strip().upper() for item in data if str(item).strip()]
    except Exception:
        return []
    return []


def _dump_ready_areas(areas: List[str]) -> str:
    normalized = []
    seen = set()
    for area in areas:
        area = str(area).strip().upper()
        if not area or area in seen:
            continue
        normalized.append(area)
        seen.add(area)
    return json.dumps(normalized, ensure_ascii=False)


def _parse_item_modifiers(raw_modifiers: Any) -> List[Dict[str, Any]]:
    if not raw_modifiers:
        return []
    if isinstance(raw_modifiers, list):
        data = raw_modifiers
    else:
        try:
            data = json.loads(raw_modifiers)
        except Exception:
            return []
    if not isinstance(data, list):
        return []
    return [entry for entry in data if isinstance(entry, dict)]


def _resolve_order_item(
    item: OrderItem,
    product_name_by_id: Dict[int, str],
    modifier_group_by_id: Dict[int, str],
    modifier_option_by_id: Dict[int, str],
) -> Dict[str, Any]:
    raw_modifiers = _parse_item_modifiers((item.modifiers or []) or item.modifiers_json)
    modifiers: List[Dict[str, str]] = []
    for modifier in raw_modifiers:
        group_id = modifier.get("group_id")
        option_id = modifier.get("option_id")
        group_name = str(
            modifier_group_by_id.get(group_id)
            or modifier.get("group_name", "")
            or ""
        ).strip()
        option_name = str(
            modifier_option_by_id.get(option_id)
            or modifier.get("option_name", modifier.get("name", ""))
            or ""
        ).strip()
        if not option_name:
            continue
        modifiers.append(
            {
                "group_name": group_name,
                "option_name": option_name,
            }
        )

    item_name = str(product_name_by_id.get(item.menu_item_id) or item.name or "").strip()
    return {
        "id": item.id,
        "item_name": item_name,
        "quantity": item.quantity,
        "modifiers": modifiers,
        "production_area": item.production_area,
    }


def _normalize_status(status: str | None) -> str:
    value = (status or "").strip().lower()
    if value in {"recebido", "pending"}:
        return "pending"
    if value in {"em_preparo", "preparo", "preparing"}:
        return "preparing"
    return (status or "").strip()


@router.get("/api/kds/orders")
def list_kds_orders(
    request: Request,
    tenant_id: int = Depends(get_request_tenant_id),
    area: str = Query("COZINHA"),
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_admin_user),
):
    require_admin_tenant_access(request=request, tenant_id=tenant_id, user=user)
    area = _normalize_area(area)

    orders = (
        db.query(Order)
        .join(OrderItem, Order.id == OrderItem.order_id)
        .filter(
            Order.tenant_id == tenant_id,
            OrderItem.production_area == area,
            func.lower(Order.status).in_(ACTIVE_STATUSES),
        )
        .order_by(desc(Order.created_at))
        .distinct()
        .all()
    )

    if not orders:
        return []

    order_ids = [order.id for order in orders]
    items = (
        db.query(OrderItem)
        .filter(
            OrderItem.tenant_id == tenant_id,
            OrderItem.order_id.in_(order_ids),
            OrderItem.production_area == area,
        )
        .order_by(OrderItem.id.asc())
        .all()
    )

    items_by_order: Dict[int, List[OrderItem]] = {}
    menu_item_ids: set[int] = set()
    modifier_group_ids: set[int] = set()
    modifier_option_ids: set[int] = set()
    for item in items:
        items_by_order.setdefault(item.order_id, []).append(item)
        if item.menu_item_id:
            menu_item_ids.add(item.menu_item_id)
        for modifier in _parse_item_modifiers((item.modifiers or []) or item.modifiers_json):
            group_id = modifier.get("group_id")
            option_id = modifier.get("option_id")
            if isinstance(group_id, int):
                modifier_group_ids.add(group_id)
            if isinstance(option_id, int):
                modifier_option_ids.add(option_id)

    product_name_by_id: Dict[int, str] = {}
    if menu_item_ids:
        product_name_by_id = {
            row.id: row.name
            for row in db.query(MenuItem.id, MenuItem.name)
            .filter(MenuItem.tenant_id == tenant_id, MenuItem.id.in_(menu_item_ids))
            .all()
        }

    modifier_group_by_id: Dict[int, str] = {}
    if modifier_group_ids:
        modifier_group_by_id = {
            row.id: row.name
            for row in db.query(ModifierGroup.id, ModifierGroup.name)
            .filter(ModifierGroup.tenant_id == tenant_id, ModifierGroup.id.in_(modifier_group_ids))
            .all()
        }

    modifier_option_by_id: Dict[int, str] = {}
    if modifier_option_ids:
        modifier_option_by_id = {
            row.id: row.name
            for row in db.query(ModifierOption.id, ModifierOption.name)
            .filter(ModifierOption.id.in_(modifier_option_ids))
            .all()
        }

    response = []
    for order in orders:
        ready_areas = _parse_ready_areas(order.production_ready_areas_json)
        resolved_items = [
            _resolve_order_item(
                item,
                product_name_by_id=product_name_by_id,
                modifier_group_by_id=modifier_group_by_id,
                modifier_option_by_id=modifier_option_by_id,
            )
            for item in items_by_order.get(order.id, [])
        ]
        response.append(
            {
                "id": order.id,
                "tenant_id": order.tenant_id,
                "status": _normalize_status(order.status),
                "created_at": order.created_at.isoformat() if order.created_at else None,
                "cliente_nome": order.cliente_nome,
                "cliente_telefone": order.cliente_telefone,
                "tipo_entrega": order.tipo_entrega,
                "order_type": order.order_type,
                "payment_method": order.payment_method,
                "street": order.street,
                "number": order.number,
                "complement": order.complement,
                "neighborhood": order.neighborhood,
                "city": order.city,
                "reference": order.reference,
                "address": {
                    "street": order.street,
                    "number": order.number,
                    "neighborhood": order.neighborhood,
                    "city": order.city,
                    "reference": order.reference,
                },
                "observacao": order.observacao,
                "resolved_items": resolved_items,
                "itens": [
                    {
                        "id": item["id"],
                        "name": item["item_name"],
                        "quantity": item["quantity"],
                        "modifiers": [
                            {
                                "name": modifier["option_name"],
                                "group_name": modifier["group_name"],
                                "option_name": modifier["option_name"],
                            }
                            for modifier in item["modifiers"]
                        ],
                        "production_area": item["production_area"],
                    }
                    for item in resolved_items
                ],
                "ready_areas": ready_areas,
            }
        )

    return response


@router.post("/api/kds/orders/{order_id}/start")
def start_kds_order(
    request: Request,
    order_id: int,
    tenant_id: int = Depends(get_request_tenant_id),
    area: str = Query("COZINHA"),
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_admin_user),
):
    require_admin_tenant_access(request=request, tenant_id=tenant_id, user=user)
    area = _normalize_area(area)

    order = db.query(Order).filter(Order.id == order_id, Order.tenant_id == tenant_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")

    has_area_items = (
        db.query(OrderItem.id)
        .filter(
            OrderItem.order_id == order_id,
            OrderItem.tenant_id == tenant_id,
            OrderItem.production_area == area,
        )
        .first()
    )
    if not has_area_items:
        raise HTTPException(status_code=400, detail="Pedido não possui itens desta área")

    current_status = _normalize_status(order.status)
    if current_status in {"PRONTO", "ENTREGUE", "SAIU", "SAIU_PARA_ENTREGA"}:
        raise HTTPException(status_code=409, detail="Pedido já finalizado")

    if current_status == "pending":
        order.status = "preparing"

    db.add(order)
    log_admin_action(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        action="kds.start",
        entity_type="order",
        entity_id=order_id,
        meta={"area": area, "from_status": current_status, "to_status": order.status},
    )
    db.commit()
    db.refresh(order)
    emit_order_status_changed(order, current_status)

    return {"ok": True, "status": _normalize_status(order.status)}


@router.post("/api/kds/orders/{order_id}/ready")
def ready_kds_order(
    request: Request,
    order_id: int,
    tenant_id: int = Depends(get_request_tenant_id),
    area: str = Query("COZINHA"),
    db: Session = Depends(get_db),
    user: AdminUser = Depends(require_admin_user),
):
    require_admin_tenant_access(request=request, tenant_id=tenant_id, user=user)
    area = _normalize_area(area)

    order = db.query(Order).filter(Order.id == order_id, Order.tenant_id == tenant_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")

    has_area_items = (
        db.query(OrderItem.id)
        .filter(
            OrderItem.order_id == order_id,
            OrderItem.tenant_id == tenant_id,
            OrderItem.production_area == area,
        )
        .first()
    )
    if not has_area_items:
        raise HTTPException(status_code=400, detail="Pedido não possui itens desta área")

    current_status = _normalize_status(order.status)
    if current_status in {"ENTREGUE", "SAIU", "SAIU_PARA_ENTREGA"}:
        raise HTTPException(status_code=409, detail="Pedido já saiu da cozinha")

    ready_areas = _parse_ready_areas(order.production_ready_areas_json)
    if area not in ready_areas:
        ready_areas.append(area)

    required_areas = (
        db.query(OrderItem.production_area)
        .filter(OrderItem.order_id == order_id, OrderItem.tenant_id == tenant_id)
        .distinct()
        .all()
    )
    required_set = {row.production_area for row in required_areas if row.production_area}

    all_ready = required_set.issubset(set(ready_areas)) if required_set else False

    if all_ready:
        order.status = "PRONTO"
        if not order.ready_at:
            order.ready_at = datetime.now(timezone.utc)
    elif current_status == "pending":
        order.status = "preparing"

    order.production_ready_areas_json = _dump_ready_areas(ready_areas)

    db.add(order)
    log_admin_action(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        action="kds.ready",
        entity_type="order",
        entity_id=order_id,
        meta={
            "area": area,
            "from_status": current_status,
            "to_status": order.status,
            "ready_areas": ready_areas,
            "required_areas": sorted(required_set),
        },
    )
    db.commit()
    db.refresh(order)
    emit_order_status_changed(order, current_status)

    return {
        "ok": True,
        "status": _normalize_status(order.status),
        "ready_areas": ready_areas,
        "required_areas": sorted(required_set),
    }


@router.get("/kds/{tenant_id}", response_class=HTMLResponse)
def kds_page(
    tenant_id: int,
    area: str = Query("COZINHA"),
    _user: AdminUser = Depends(get_current_admin_user_ui),
):
    area = _normalize_area(area)
    html = f"""
<!doctype html>
<html lang=\"pt-br\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />
  <title>KDS • {area} (Tenant {tenant_id})</title>
  <style>
    :root {{
      --bg: #0b0f14;
      --panel: #111827;
      --card: #1f2937;
      --text: #f8fafc;
      --muted: #94a3b8;
      --border: rgba(148,163,184,0.2);
      --accent: #f97316;
      --ok: #22c55e;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: "Inter", system-ui, -apple-system, sans-serif;
    }}
    header {{
      padding: 18px 22px;
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }}
    .title {{
      display: flex;
      flex-direction: column;
      gap: 4px;
    }}
    .title h1 {{
      margin: 0;
      font-size: 22px;
      letter-spacing: .4px;
    }}
    .title span {{
      color: var(--muted);
      font-size: 13px;
    }}
    .pill {{
      padding: 6px 12px;
      border-radius: 999px;
      background: rgba(148,163,184,0.12);
      border: 1px solid var(--border);
      font-size: 12px;
      color: var(--muted);
    }}
    main {{
      padding: 18px;
    }}
    .board {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
      min-height: calc(100vh - 120px);
    }}
    .column {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 14px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }}
    .column h2 {{
      margin: 0;
      font-size: 16px;
      letter-spacing: .5px;
      color: var(--muted);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .count {{
      background: rgba(148,163,184,0.1);
      border: 1px solid var(--border);
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 12px;
      color: var(--muted);
    }}
    .card {{
      background: var(--card);
      border-radius: 16px;
      padding: 16px;
      border: 1px solid rgba(255,255,255,0.05);
      box-shadow: 0 10px 24px rgba(0,0,0,0.35);
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}
    .card strong {{
      font-size: 18px;
    }}
    .meta {{
      display: flex;
      justify-content: space-between;
      color: var(--muted);
      font-size: 12px;
    }}
    .items {{
      font-size: 15px;
      line-height: 1.4;
      white-space: pre-wrap;
    }}
    .obs {{
      background: rgba(248,113,113,0.15);
      border: 1px solid rgba(248,113,113,0.3);
      padding: 8px 10px;
      border-radius: 12px;
      font-size: 13px;
    }}
    .actions {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    button {{
      border: none;
      border-radius: 12px;
      padding: 10px 14px;
      font-size: 14px;
      cursor: pointer;
      background: rgba(148,163,184,0.16);
      color: var(--text);
    }}
    button.primary {{
      background: rgba(249,115,22,0.25);
      border: 1px solid rgba(249,115,22,0.45);
    }}
    button.ok {{
      background: rgba(34,197,94,0.25);
      border: 1px solid rgba(34,197,94,0.45);
    }}
    @media (max-width: 920px) {{
      .board {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
<header>
  <div class=\"title\">
    <h1>KDS • {area}</h1>
    <span>Tenant {tenant_id} • Atualização automática a cada 5s</span>
  </div>
  <div class=\"pill\" id=\"status-pill\">Sincronizando…</div>
</header>

<main>
  <div class=\"board\">
    <section class=\"column\">
      <h2>Recebidos <span class=\"count\" id=\"count-recebido\">0</span></h2>
      <div id=\"list-recebido\"></div>
    </section>
    <section class=\"column\">
      <h2>Em preparo <span class=\"count\" id=\"count-preparo\">0</span></h2>
      <div id=\"list-preparo\"></div>
    </section>
  </div>
</main>

<script>
const TENANT_ID = {tenant_id};
const AREA = "{area}";

function formatTime(iso) {{
  if (!iso) return "";
  try {{
    const d = new Date(iso);
    return d.toLocaleTimeString([], {{hour: '2-digit', minute: '2-digit'}});
  }} catch (e) {{
    return "";
  }}
}}

function formatItems(items) {{
  if (!items || !items.length) return "";
  return items.map(item => {{
    const mods = (item.modifiers || []).map(m => m.name).filter(Boolean);
    const suffix = mods.length ? ` (${mods.join(', ')})` : "";
    return `${{item.quantity}}x ${{item.name}}${{suffix}}`;
  }}).join("\n");
}}

function renderCard(order, mode) {{
  const itemsText = formatItems(order.itens);
  const observacao = (order.observacao || "").trim();
  const showObs = observacao && observacao.toLowerCase() !== "sem observações" && observacao.toLowerCase() !== "sem observacoes";
  return `
    <div class=\"card\">
      <div class=\"meta\">
        <span><strong>#${{order.id}}</strong> • ${{formatTime(order.created_at)}} • ${{order.tipo_entrega || ''}}</span>
        <span>${{order.cliente_nome || 'Cliente'}}${{order.cliente_telefone ? ` • ${{order.cliente_telefone}}` : ''}}</span>
      </div>
      <div class=\"items\">${{itemsText || 'Sem itens na área'}} </div>
      ${{showObs ? `<div class=\"obs\">⚠ ${observacao}</div>` : ''}}
      <div class=\"actions\">
        ${{mode === 'recebido' ? `<button class=\"primary\" onclick=\"startOrder(${{order.id}})\">Iniciar</button>` : ''}}
        <button class=\"ok\" onclick=\"readyOrder(${{order.id}})\">Pronto</button>
      </div>
    </div>
  `;
}}

function setStatus(text) {{
  const pill = document.getElementById('status-pill');
  pill.textContent = text;
}}

async function loadOrders() {{
  try {{
    const res = await fetch(`/api/kds/orders?tenant_id=${{TENANT_ID}}&area=${{AREA}}`);
    if (!res.ok) {{
      setStatus('Erro ao carregar pedidos');
      return;
    }}
    const data = await res.json();
    const recebido = data.filter(o => o.status === 'pending');
    const preparo = data.filter(o => o.status === 'preparing');

    document.getElementById('list-recebido').innerHTML = recebido.map(o => renderCard(o, 'recebido')).join('');
    document.getElementById('list-preparo').innerHTML = preparo.map(o => renderCard(o, 'preparo')).join('');

    document.getElementById('count-recebido').textContent = recebido.length;
    document.getElementById('count-preparo').textContent = preparo.length;

    setStatus(`Atualizado • ${{new Date().toLocaleTimeString([], {{hour: '2-digit', minute: '2-digit'}})}}`);
  }} catch (e) {{
    setStatus('Sem conexão');
  }}
}}

async function startOrder(orderId) {{
  try {{
    const res = await fetch(`/api/kds/orders/${{orderId}}/start?tenant_id=${{TENANT_ID}}&area=${{AREA}}`, {{ method: 'POST' }});
    if (!res.ok) {{
      const text = await res.text();
      alert(text || 'Erro ao iniciar');
    }}
  }} catch (e) {{
    alert('Falha na rede ao iniciar');
  }}
  await loadOrders();
}}

async function readyOrder(orderId) {{
  try {{
    const res = await fetch(`/api/kds/orders/${{orderId}}/ready?tenant_id=${{TENANT_ID}}&area=${{AREA}}`, {{ method: 'POST' }});
    if (!res.ok) {{
      const text = await res.text();
      alert(text || 'Erro ao finalizar');
    }}
  }} catch (e) {{
    alert('Falha na rede ao finalizar');
  }}
  await loadOrders();
}}

loadOrders();
setInterval(loadOrders, 5000);
</script>
</body>
</html>
"""
    return HTMLResponse(html)


@router.get("/painel/{tenant_id}", response_class=HTMLResponse)
def kds_legacy_page(tenant_id: int, area: str = Query("COZINHA")):
    html = (
        f"<html><head><meta http-equiv=\"refresh\" content=\"0; url=/kds/{tenant_id}?area={area}\" /></head>"
        "<body>Redirecionando…</body></html>"
    )
    return HTMLResponse(html)
