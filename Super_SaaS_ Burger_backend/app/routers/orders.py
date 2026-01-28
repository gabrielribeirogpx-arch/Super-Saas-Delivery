from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc
import json
from typing import Any, Dict, List, Optional

from app.core.database import get_db
from app.models.order import Order
from app.models.order_item import OrderItem
from app.integrations.whatsapp import send_text
from app.services.printing import auto_print_if_possible, get_print_settings
from app.services.orders import create_order_items

router = APIRouter(prefix="/api", tags=["orders"])


def _safe_json_load(value: Any):
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return value
        try:
            return json.loads(s)
        except Exception:
            return value
    return value


def _order_to_dict(o: Order) -> Dict[str, Any]:
    return {
        "id": o.id,
        "tenant_id": o.tenant_id,
        "cliente_nome": o.cliente_nome,
        "cliente_telefone": o.cliente_telefone,
        "itens": _safe_json_load(o.itens),
        "items_json": _safe_json_load(o.items_json),
        "endereco": o.endereco,
        "observacao": o.observacao,
        "tipo_entrega": o.tipo_entrega,
        "forma_pagamento": o.forma_pagamento,
        "valor_total": o.valor_total,
        "total_cents": o.total_cents,
        "status": o.status,
        "created_at": o.created_at.isoformat() if o.created_at else None,
    }


def _order_item_to_dict(item: OrderItem) -> Dict[str, Any]:
    return {
        "id": item.id,
        "tenant_id": item.tenant_id,
        "order_id": item.order_id,
        "menu_item_id": item.menu_item_id,
        "name": item.name,
        "quantity": item.quantity,
        "unit_price_cents": item.unit_price_cents,
        "total_price_cents": item.subtotal_cents,
        "subtotal_cents": item.subtotal_cents,
        "modifiers": _safe_json_load(item.modifiers_json),
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


@router.get("/orders/{tenant_id}")
def list_orders(tenant_id: int, db: Session = Depends(get_db)):
    orders = (
        db.query(Order)
        .filter(Order.tenant_id == tenant_id)
        .order_by(desc(Order.created_at))
        .all()
    )
    return [_order_to_dict(o) for o in orders]


class OrderItem(BaseModel):
    menu_item_id: Optional[int] = None
    nome: str
    qtd: int = Field(..., ge=1)
    preco: float = Field(..., ge=0)
    modifiers: Optional[List[Dict[str, Any]]] = None


class OrderCreate(BaseModel):
    cliente_nome: str
    cliente_telefone: str
    itens: List[OrderItem]
    endereco: str
    observacao: Optional[str] = None
    tipo_entrega: str
    forma_pagamento: str
    valor_total: float = Field(..., ge=0)


@router.post("/orders/{tenant_id}")
def create_order(
    tenant_id: int,
    payload: OrderCreate,
    db: Session = Depends(get_db),
):
    # salva itens como JSON no banco (Order.itens é Text)
    items_structured = []
    total_cents = 0
    for item in payload.itens:
        unit_price_cents = int(round(item.preco * 100))
        modifiers = item.modifiers or []
        modifiers_total_cents = 0
        normalized_modifiers: List[Dict[str, Any]] = []
        for modifier in modifiers:
            name = str(modifier.get("name", "") or "").strip()
            price_cents = int(modifier.get("price_cents", 0) or 0)
            if name:
                normalized_modifiers.append(
                    {
                        "name": name,
                        "price_cents": price_cents,
                    }
                )
                modifiers_total_cents += price_cents

        unit_with_modifiers = unit_price_cents + modifiers_total_cents
        subtotal_cents = unit_with_modifiers * item.qtd
        total_cents += subtotal_cents
        items_structured.append(
            {
                "menu_item_id": item.menu_item_id,
                "name": item.nome,
                "quantity": item.qtd,
                "unit_price_cents": unit_price_cents,
                "modifiers": normalized_modifiers,
                "modifiers_total_cents": modifiers_total_cents,
                "subtotal_cents": subtotal_cents,
            }
        )

    itens_json = json.dumps(items_structured, ensure_ascii=False)
    itens_text_parts = []
    for item in payload.itens:
        suffix = ""
        if item.modifiers:
            names = [str(m.get("name", "") or "").strip() for m in item.modifiers if m.get("name")]
            if names:
                suffix = f" ({', '.join(names)})"
        itens_text_parts.append(f"{item.qtd}x {item.nome}{suffix}")
    itens_text = ", ".join(itens_text_parts)

    order = Order(
        tenant_id=tenant_id,
        cliente_nome=payload.cliente_nome,
        cliente_telefone=payload.cliente_telefone,
        itens=itens_text,
        items_json=itens_json,
        endereco=payload.endereco,
        observacao=payload.observacao,
        tipo_entrega=payload.tipo_entrega,
        forma_pagamento=payload.forma_pagamento,
        valor_total=total_cents,
        total_cents=total_cents,
        status="RECEBIDO",
    )

    db.add(order)
    db.flush()
    if items_structured:
        create_order_items(db, tenant_id=tenant_id, order_id=order.id, items_structured=items_structured)
    db.commit()
    db.refresh(order)

    try:
        print_settings = get_print_settings(tenant_id)
        auto_print_if_possible(order, tenant_id, config=print_settings)
    except Exception as exc:
        print("ERRO AO GERAR/IMPRIMIR ETIQUETA:", str(exc))

    return _order_to_dict(order)


@router.get("/orders/{order_id}/items")
def list_order_items(order_id: int, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    items = (
        db.query(OrderItem)
        .filter(OrderItem.order_id == order_id, OrderItem.tenant_id == order.tenant_id)
        .order_by(OrderItem.id.asc())
        .all()
    )
    return [_order_item_to_dict(item) for item in items]


class StatusUpdate(BaseModel):
    status: str


def status_message(status: str):
    status = status.upper()

    if status == "PREPARO":
        return "👨‍🍳 Seu pedido entrou em preparo!"
    if status == "PRONTO":
        return "🍔✅ Seu pedido está pronto!"
    if status in {"SAIU", "SAIU_PARA_ENTREGA"}:
        return "🛵 Seu pedido saiu para entrega!"
    if status == "ENTREGUE":
        return "📦 Pedido entregue! Obrigado!"
    return None


@router.patch("/orders/{order_id}/status")
def update_status(
    order_id: int,
    body: StatusUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    new_status = body.status.upper()

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")

    if order.status == new_status:
        return {"ok": True}

    order.status = new_status
    db.commit()
    db.refresh(order)

    msg = status_message(new_status)

    # 📲 WhatsApp em background (não trava o Kanban)
    if msg and order.cliente_telefone:
        background_tasks.add_task(
            send_text,
            to=order.cliente_telefone,
            text=f"Pedido #{order.id}\n{msg}",
        )

    return {"ok": True, "status": new_status}


@router.get("/orders/{tenant_id}/delivery")
def list_delivery_orders(
    tenant_id: int,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    if status:
        statuses = [s.strip().upper() for s in status.split(",") if s.strip()]
    else:
        statuses = ["PRONTO", "SAIU_PARA_ENTREGA"]

    if "SAIU_PARA_ENTREGA" in statuses and "SAIU" not in statuses:
        statuses.append("SAIU")

    query = db.query(Order).filter(Order.tenant_id == tenant_id)
    if statuses:
        query = query.filter(Order.status.in_(statuses))

    orders = query.order_by(desc(Order.created_at)).all()
    return [_order_to_dict(o) for o in orders]
