from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_delivery_user
from app.models.order import Order
from app.models.user import User

router = APIRouter(prefix="/api/delivery", tags=["delivery-api"])

READY_STATUSES = {"READY", "PRONTO"}
OUT_FOR_DELIVERY_STATUSES = {"OUT_FOR_DELIVERY", "SAIU", "SAIU_PARA_ENTREGA"}
DELIVERED_STATUSES = {"DELIVERED", "ENTREGUE"}


def _order_to_delivery_dict(order: Order) -> Dict[str, Any]:
    return {
        "id": order.id,
        "tenant_id": order.tenant_id,
        "status": order.status,
        "cliente_nome": order.cliente_nome,
        "cliente_telefone": order.cliente_telefone,
        "itens": order.itens,
        "endereco": order.endereco,
        "observacao": order.observacao,
        "ready_at": order.ready_at.isoformat() if order.ready_at else None,
        "start_delivery_at": order.start_delivery_at.isoformat() if order.start_delivery_at else None,
        "assigned_delivery_user_id": order.assigned_delivery_user_id,
        "created_at": order.created_at.isoformat() if order.created_at else None,
    }


def _expand_statuses(raw_status: Optional[str]) -> List[str]:
    if raw_status:
        statuses = [s.strip().upper() for s in raw_status.split(",") if s.strip()]
    else:
        statuses = sorted(READY_STATUSES | {"OUT_FOR_DELIVERY"})

    expanded_statuses: List[str] = []
    for current in statuses:
        if current == "READY":
            expanded_statuses.extend(sorted(READY_STATUSES))
            continue
        if current == "OUT_FOR_DELIVERY":
            expanded_statuses.extend(sorted(OUT_FOR_DELIVERY_STATUSES))
            continue
        if current == "DELIVERED":
            expanded_statuses.extend(sorted(DELIVERED_STATUSES))
            continue
        expanded_statuses.append(current)

    return sorted(set(expanded_statuses))


@router.get("/orders")
def list_delivery_orders(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_delivery_user),
):
    tenant_id = int(current_user.tenant_id)
    normalized_statuses = _expand_statuses(status)

    query = db.query(Order).filter(Order.tenant_id == tenant_id)
    if normalized_statuses:
        query = query.filter(Order.status.in_(normalized_statuses))

    orders = query.order_by(desc(Order.created_at)).all()
    return [_order_to_delivery_dict(order) for order in orders]


@router.patch("/orders/{order_id}/start")
def start_delivery_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_delivery_user),
):
    tenant_id = int(current_user.tenant_id)
    order = db.query(Order).filter(Order.id == order_id, Order.tenant_id == tenant_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")

    current_status = (order.status or "").upper()
    if current_status in DELIVERED_STATUSES:
        raise HTTPException(status_code=409, detail="Pedido já foi entregue")

    if order.assigned_delivery_user_id and int(order.assigned_delivery_user_id) != int(current_user.id):
        raise HTTPException(status_code=409, detail="Pedido já atribuído para outro entregador")

    if current_status in OUT_FOR_DELIVERY_STATUSES:
        return {"ok": True, "status": "OUT_FOR_DELIVERY"}

    if current_status not in READY_STATUSES:
        raise HTTPException(status_code=409, detail="Pedido ainda não está pronto para entrega")

    order.assigned_delivery_user_id = int(current_user.id)
    if not order.start_delivery_at:
        order.start_delivery_at = datetime.now(timezone.utc)
    order.status = "OUT_FOR_DELIVERY"
    db.commit()

    return {"ok": True, "status": order.status, "assigned_delivery_user_id": order.assigned_delivery_user_id}


@router.patch("/orders/{order_id}/complete")
def complete_delivery_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_delivery_user),
):
    tenant_id = int(current_user.tenant_id)
    order = db.query(Order).filter(Order.id == order_id, Order.tenant_id == tenant_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")

    if order.assigned_delivery_user_id and int(order.assigned_delivery_user_id) != int(current_user.id):
        raise HTTPException(status_code=409, detail="Pedido atribuído para outro entregador")

    current_status = (order.status or "").upper()
    if current_status in DELIVERED_STATUSES:
        return {"ok": True, "status": "DELIVERED"}

    if current_status not in OUT_FOR_DELIVERY_STATUSES:
        raise HTTPException(status_code=409, detail="Pedido ainda não saiu para entrega")

    order.assigned_delivery_user_id = int(current_user.id)
    order.status = "DELIVERED"
    db.commit()

    return {"ok": True, "status": order.status, "assigned_delivery_user_id": order.assigned_delivery_user_id}
