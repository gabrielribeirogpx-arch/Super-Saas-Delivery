from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc
import json
from typing import Any, Dict, List, Optional

from app.core.database import get_db
from app.models.order import Order
from app.integrations.whatsapp import send_text
from app.services.printing import generate_ticket_pdf

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
        "endereco": o.endereco,
        "observacao": o.observacao,
        "tipo_entrega": o.tipo_entrega,
        "forma_pagamento": o.forma_pagamento,
        "valor_total": o.valor_total,
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
    itens_json = json.dumps([i.model_dump() for i in payload.itens], ensure_ascii=False)

    order = Order(
        tenant_id=tenant_id,
        cliente_nome=payload.cliente_nome,
        cliente_telefone=payload.cliente_telefone,
        itens=itens_json,
        endereco=payload.endereco,
        observacao=payload.observacao,
        tipo_entrega=payload.tipo_entrega,
        forma_pagamento=payload.forma_pagamento,
        valor_total=payload.valor_total,
        status="NOVO",
    )

    db.add(order)
    db.commit()
    db.refresh(order)

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

    # 🧾 Etiqueta quando entra em preparo
    if new_status == "PREPARO":
        background_tasks.add_task(generate_ticket_pdf, order)

    return {"ok": True, "status": new_status}
