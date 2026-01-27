from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc
import json
from typing import Any, Dict, List, Optional

from app.core.database import get_db
from app.models.order import Order
from app.integrations.whatsapp import send_text
from app.services.printing import auto_print_if_possible, get_print_settings

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
        subtotal_cents = unit_price_cents * item.qtd
        total_cents += subtotal_cents
        items_structured.append(
            {
                "menu_item_id": item.menu_item_id,
                "name": item.nome,
                "quantity": item.qtd,
                "unit_price_cents": unit_price_cents,
                "subtotal_cents": subtotal_cents,
            }
        )

    itens_json = json.dumps(items_structured, ensure_ascii=False)
    itens_text = ", ".join(f"{item.qtd}x {item.nome}" for item in payload.itens)

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
    db.commit()
    db.refresh(order)

    try:
        print_settings = get_print_settings(tenant_id)
        auto_print_if_possible(order, tenant_id, config=print_settings)
    except Exception as exc:
        print("ERRO AO GERAR/IMPRIMIR ETIQUETA:", str(exc))

    return _order_to_dict(order)


class StatusUpdate(BaseModel):
    status: str


def status_message(status: str):
    status = status.upper()

    if status == "PREPARO":
        return "👨‍🍳 Seu pedido entrou em preparo!"
    if status == "PRONTO":
        return "🍔✅ Seu pedido está pronto!"
    if status == "SAIU":
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
