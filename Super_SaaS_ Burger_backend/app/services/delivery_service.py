from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import HTTPException
from sqlalchemy import and_, desc, exists, func, update
from sqlalchemy.orm import Session

from app.models.admin_user import AdminUser
from app.models.delivery_log import DeliveryLog
from app.models.delivery_tracking import DeliveryTracking
from app.models.order import Order
from app.realtime.publisher import publish_public_tracking_event, publish_standard_delivery_status_event
from app.services.order_events import emit_order_status_changed

OFFLINE = "OFFLINE"
ONLINE = "ONLINE"
DELIVERING = "DELIVERING"

READY_STATUSES = {"READY", "PRONTO"}
OUT_FOR_DELIVERY_STATUSES = {"OUT_FOR_DELIVERY", "SAIU", "SAIU_PARA_ENTREGA"}
DELIVERED_STATUSES = {"DELIVERED", "ENTREGUE"}


def _status_or_default(user: AdminUser) -> str:
    return str(getattr(user, "status", OFFLINE) or OFFLINE).upper()


def _create_delivery_log(
    db: Session,
    *,
    tenant_id: int,
    order_id: int,
    delivery_user_id: int,
    event_type: str,
    metadata_json: Dict[str, Any] | None = None,
) -> None:
    db.add(
        DeliveryLog(
            tenant_id=tenant_id,
            order_id=order_id,
            delivery_user_id=delivery_user_id,
            event_type=event_type,
            metadata_json=metadata_json,
        )
    )


def _active_order_exists(db: Session, *, tenant_id: int, delivery_user_id: int) -> bool:
    condition = (
        db.query(Order.id)
        .filter(
            Order.tenant_id == int(tenant_id),
            Order.assigned_delivery_user_id == int(delivery_user_id),
            func.upper(Order.status).in_(OUT_FOR_DELIVERY_STATUSES),
        )
        .exists()
    )
    return bool(db.query(condition).scalar())


def set_online(db: Session, *, current_user: AdminUser) -> Dict[str, Any]:
    current_status = _status_or_default(current_user)
    if current_status == DELIVERING:
        raise HTTPException(status_code=409, detail="Entregador em rota não pode alterar para ONLINE")

    current_user.status = ONLINE
    db.add(current_user)
    db.commit()
    db.refresh(current_user)

    publish_standard_delivery_status_event(
        tenant_id=int(current_user.tenant_id),
        delivery_user_id=int(current_user.id),
        status=current_user.status,
    )
    return {"ok": True, "status": current_user.status}


def set_offline(db: Session, *, current_user: AdminUser) -> Dict[str, Any]:
    if _status_or_default(current_user) == DELIVERING:
        raise HTTPException(status_code=409, detail="Entregador não pode ficar offline durante entrega")

    current_user.status = OFFLINE
    db.add(current_user)
    db.commit()
    db.refresh(current_user)

    publish_standard_delivery_status_event(
        tenant_id=int(current_user.tenant_id),
        delivery_user_id=int(current_user.id),
        status=current_user.status,
    )
    return {"ok": True, "status": current_user.status}


def list_available_orders(db: Session, *, current_user: AdminUser) -> List[Order]:
    return (
        db.query(Order)
        .filter(
            Order.tenant_id == int(current_user.tenant_id),
            func.upper(Order.status).in_(READY_STATUSES),
            Order.assigned_delivery_user_id.is_(None),
        )
        .order_by(desc(Order.created_at))
        .all()
    )


def accept_order(db: Session, *, current_user: AdminUser, order_id: int) -> Dict[str, Any]:
    tenant_id = int(current_user.tenant_id)
    delivery_user_id = int(current_user.id)

    status_update = (
        update(AdminUser)
        .where(
            AdminUser.id == delivery_user_id,
            AdminUser.tenant_id == tenant_id,
            func.upper(AdminUser.role) == "DELIVERY",
            func.upper(AdminUser.status) == ONLINE,
        )
        .values(status=DELIVERING)
    )
    status_result = db.execute(status_update)
    if int(getattr(status_result, "rowcount", 0) or 0) != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Somente entregador ONLINE pode aceitar pedido")

    if _active_order_exists(db, tenant_id=tenant_id, delivery_user_id=delivery_user_id):
        db.rollback()
        raise HTTPException(status_code=409, detail="Entregador já possui pedido ativo")

    now = datetime.now(timezone.utc)
    order_update = (
        update(Order)
        .where(
            Order.id == int(order_id),
            Order.tenant_id == tenant_id,
            func.upper(Order.status).in_(READY_STATUSES),
            Order.assigned_delivery_user_id.is_(None),
        )
        .values(
            assigned_delivery_user_id=delivery_user_id,
            status="OUT_FOR_DELIVERY",
            start_delivery_at=func.coalesce(Order.start_delivery_at, now),
        )
    )

    order_result = db.execute(order_update)
    if int(getattr(order_result, "rowcount", 0) or 0) != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Pedido indisponível para aceite")

    order = (
        db.query(Order)
        .filter(
            Order.id == int(order_id),
            Order.tenant_id == tenant_id,
            Order.assigned_delivery_user_id == delivery_user_id,
        )
        .first()
    )
    if order is None:
        db.rollback()
        raise HTTPException(status_code=404, detail="Pedido não encontrado")

    _create_delivery_log(
        db,
        tenant_id=tenant_id,
        order_id=int(order.id),
        delivery_user_id=delivery_user_id,
        event_type="started",
    )

    db.commit()
    emit_order_status_changed(order, "READY")
    publish_standard_delivery_status_event(tenant_id=tenant_id, delivery_user_id=delivery_user_id, status=DELIVERING)
    return {"ok": True, "status": order.status, "assigned_delivery_user_id": order.assigned_delivery_user_id}


def complete_delivery(db: Session, *, current_user: AdminUser, order_id: int) -> Dict[str, Any]:
    tenant_id = int(current_user.tenant_id)
    delivery_user_id = int(current_user.id)

    order = (
        db.query(Order)
        .filter(Order.id == int(order_id), Order.tenant_id == tenant_id)
        .first()
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")

    if int(order.assigned_delivery_user_id or 0) != delivery_user_id:
        raise HTTPException(status_code=409, detail="Pedido atribuído para outro entregador")

    if str(order.status or "").upper() in DELIVERED_STATUSES:
        return {"ok": True, "status": "DELIVERED", "assigned_delivery_user_id": order.assigned_delivery_user_id}

    if str(order.status or "").upper() not in OUT_FOR_DELIVERY_STATUSES:
        raise HTTPException(status_code=409, detail="Pedido ainda não saiu para entrega")

    tracking = (
        db.query(DeliveryTracking)
        .join(Order, Order.id == DeliveryTracking.order_id)
        .filter(
            DeliveryTracking.order_id == int(order.id),
            Order.tenant_id == tenant_id,
        )
        .first()
    )
    if tracking is not None and getattr(tracking, "completed_at", None) is None:
        tracking.completed_at = datetime.now(timezone.utc)

    previous_status = order.status
    order.status = "DELIVERED"
    _create_delivery_log(
        db,
        tenant_id=tenant_id,
        order_id=int(order.id),
        delivery_user_id=delivery_user_id,
        event_type="completed",
    )

    has_other_active_orders = (
        db.query(
            exists().where(
                and_(
                    Order.tenant_id == tenant_id,
                    Order.assigned_delivery_user_id == delivery_user_id,
                    Order.id != int(order.id),
                    func.upper(Order.status).in_(OUT_FOR_DELIVERY_STATUSES),
                )
            )
        ).scalar()
        is True
    )

    if not has_other_active_orders:
        current_user.status = ONLINE
        db.add(current_user)

    db.commit()
    emit_order_status_changed(order, previous_status)
    publish_standard_delivery_status_event(
        tenant_id=tenant_id,
        delivery_user_id=delivery_user_id,
        status=_status_or_default(current_user),
    )
    publish_public_tracking_event(
        tenant_id=tenant_id,
        order_id=int(order.id),
        status=order.status,
        delivery_user_name=getattr(current_user, "name", None),
        lat=0.0,
        lng=0.0,
    )
    return {"ok": True, "status": order.status, "assigned_delivery_user_id": order.assigned_delivery_user_id}
