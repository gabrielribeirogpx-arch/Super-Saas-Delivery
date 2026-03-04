from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import require_delivery_user
from app.models.admin_user import AdminUser
from app.models.delivery_log import DeliveryLog
from app.models.delivery_tracking import DeliveryTracking
from app.models.order import Order
from app.realtime.publisher import publish_delivery_location_event, publish_public_tracking_event
from app.services.auth import create_access_token
from app.services.order_events import emit_order_status_changed
from app.services.delivery_service import (
    accept_order as dispatch_accept_order,
    complete_delivery as dispatch_complete_delivery,
    list_available_orders as dispatch_list_available_orders,
    set_offline as dispatch_set_offline,
    set_online as dispatch_set_online,
)
from app.services.eta_service import calculate_eta
from app.services.passwords import verify_password

router = APIRouter(prefix="/api/delivery", tags=["delivery-api"])
logger = logging.getLogger(__name__)

READY_STATUSES = {"READY", "PRONTO"}
OUT_FOR_DELIVERY_STATUSES = {"OUT_FOR_DELIVERY", "SAIU", "SAIU_PARA_ENTREGA"}
DELIVERED_STATUSES = {"DELIVERED", "ENTREGUE"}


class DeliveryLoginPayload(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


class DeliveryLocationPayload(BaseModel):
    order_id: int
    latitude: float
    longitude: float


def _create_delivery_log(
    db: Session,
    *,
    tenant_id: int,
    order_id: int,
    delivery_user_id: int,
    event_type: str,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    metadata_json: Optional[Dict[str, Any]] = None,
) -> None:
    db.add(
        DeliveryLog(
            tenant_id=tenant_id,
            order_id=order_id,
            delivery_user_id=delivery_user_id,
            event_type=event_type,
            latitude=latitude,
            longitude=longitude,
            metadata_json=metadata_json,
        )
    )


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


@router.post("/login", include_in_schema=False)
def delivery_login(
    payload: DeliveryLoginPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    tenant = getattr(request.state, "tenant", None)
    if tenant is None:
        raise HTTPException(status_code=400, detail="Não foi possível resolver o tenant para login.")

    matched_user = (
        db.query(AdminUser)
        .filter(
            AdminUser.tenant_id == int(tenant.id),
            func.upper(AdminUser.role) == "DELIVERY",
            AdminUser.active.is_(True),
            func.lower(AdminUser.email) == payload.email.lower(),
        )
        .first()
    )

    password_is_valid = matched_user is not None and verify_password(payload.password, matched_user.password_hash)
    if not matched_user or not password_is_valid:
        logger.warning(
            "event=delivery_auth_login_failed tenant_id=%s email=%s",
            int(tenant.id),
            payload.email,
        )
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    token = create_access_token(
        str(matched_user.id),
        extra={
            "tenant_id": int(matched_user.tenant_id),
            "delivery_user_id": int(matched_user.id),
            "role": "delivery",
        },
    )

    logger.info(
        "event=delivery_auth_login_success tenant_id=%s delivery_user_id=%s",
        int(matched_user.tenant_id),
        int(matched_user.id),
    )

    return {
        "access_token": token,
        "token_type": "bearer",
    }


@router.post("/auth/login")
def delivery_auth_login(
    payload: DeliveryLoginPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    return delivery_login(payload=payload, request=request, db=db)




@router.post("/status/online")
def set_delivery_online(
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(require_delivery_user),
):
    return dispatch_set_online(db, current_user=current_user)


@router.post("/status/offline")
def set_delivery_offline(
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(require_delivery_user),
):
    return dispatch_set_offline(db, current_user=current_user)


@router.get("/available-orders")
def list_available_delivery_orders(
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(require_delivery_user),
):
    orders = dispatch_list_available_orders(db, current_user=current_user)
    return [_order_to_delivery_dict(order) for order in orders]


@router.post("/orders/{order_id}/accept")
def accept_delivery_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(require_delivery_user),
):
    return dispatch_accept_order(db, current_user=current_user, order_id=order_id)


@router.post("/orders/{order_id}/complete")
def complete_delivery_order_v2(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(require_delivery_user),
):
    return dispatch_complete_delivery(db, current_user=current_user, order_id=order_id)

@router.get("/orders")
def list_delivery_orders(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(require_delivery_user),
):
    tenant_id = int(current_user.tenant_id)
    normalized_statuses = _expand_statuses(status)

    query = db.query(Order).filter(
        Order.tenant_id == tenant_id,
        Order.assigned_delivery_user_id == int(current_user.id),
    )
    if normalized_statuses:
        query = query.filter(Order.status.in_(normalized_statuses))

    orders = query.order_by(desc(Order.created_at)).all()
    return [_order_to_delivery_dict(order) for order in orders]


@router.post("/{order_id}/start")
@router.patch("/orders/{order_id}/start", include_in_schema=False)
def start_delivery_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(require_delivery_user),
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

    previous_status = order.status
    order.assigned_delivery_user_id = int(current_user.id)
    if not order.start_delivery_at:
        order.start_delivery_at = datetime.now(timezone.utc)

    estimated_seconds = calculate_eta(order)
    tracking = db.query(DeliveryTracking).filter(DeliveryTracking.order_id == order.id).first()
    if tracking is None:
        now_utc = datetime.now(timezone.utc)
        db.add(
            DeliveryTracking(
                started_at=now_utc,
                estimated_duration_seconds=estimated_seconds,
                expected_delivery_at=now_utc + timedelta(seconds=estimated_seconds),
                delivery_user_id=int(current_user.id),
                order_id=order.id,
            )
        )

    order.status = "OUT_FOR_DELIVERY"
    _create_delivery_log(
        db,
        tenant_id=tenant_id,
        order_id=order.id,
        delivery_user_id=int(current_user.id),
        event_type="started",
    )
    db.commit()

    emit_order_status_changed(order, previous_status)
    return {"ok": True, "status": order.status, "assigned_delivery_user_id": order.assigned_delivery_user_id}


@router.post("/{order_id}/complete")
@router.patch("/orders/{order_id}/complete", include_in_schema=False)
def complete_delivery_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(require_delivery_user),
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

    previous_status = order.status
    order.assigned_delivery_user_id = int(current_user.id)
    order.status = "DELIVERED"
    _create_delivery_log(
        db,
        tenant_id=tenant_id,
        order_id=order.id,
        delivery_user_id=int(current_user.id),
        event_type="completed",
    )
    db.commit()

    emit_order_status_changed(order, previous_status)
    return {"ok": True, "status": order.status, "assigned_delivery_user_id": order.assigned_delivery_user_id}


@router.post("/location", include_in_schema=False)
def create_delivery_location_log(
    payload: DeliveryLocationPayload,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(require_delivery_user),
):
    tenant_id = int(current_user.tenant_id)
    order = db.query(Order).filter(Order.id == payload.order_id, Order.tenant_id == tenant_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")

    if not order.assigned_delivery_user_id or int(order.assigned_delivery_user_id) != int(current_user.id):
        raise HTTPException(status_code=409, detail="Pedido atribuído para outro entregador")

    _create_delivery_log(
        db,
        tenant_id=tenant_id,
        order_id=order.id,
        delivery_user_id=int(current_user.id),
        event_type="location_update",
        latitude=payload.latitude,
        longitude=payload.longitude,
    )
    db.commit()

    publish_delivery_location_event(
        tenant_id=tenant_id,
        delivery_user_id=int(current_user.id),
        lat=payload.latitude,
        lng=payload.longitude,
        order_id=int(order.id),
    )

    current_status = (order.status or "").upper()
    if current_status in OUT_FOR_DELIVERY_STATUSES:
        publish_public_tracking_event(
            tenant_id=tenant_id,
            order_id=int(order.id),
            status=order.status,
            delivery_user_name=getattr(current_user, "name", None),
            lat=payload.latitude,
            lng=payload.longitude,
        )

    return {"ok": True}
