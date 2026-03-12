from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import get_current_delivery_user
from app.models.admin_user import AdminUser
from app.models.delivery_tracking import DeliveryTracking
from app.models.order import Order
from app.services.auth import create_access_token
from app.realtime.publisher import publish_delivery_driver_location_event
from app.services.order_events import emit_order_status_changed
from app.services.passwords import verify_password

router = APIRouter(prefix="/api/driver", tags=["driver-app"])
logger = logging.getLogger(__name__)

READY_FOR_DELIVERY_STATUSES = {"READY_FOR_DELIVERY", "READY", "PRONTO"}
DRIVER_ASSIGNED_STATUSES = {"DRIVER_ASSIGNED"}
OUT_FOR_DELIVERY_STATUSES = {"OUT_FOR_DELIVERY", "SAIU", "SAIU_PARA_ENTREGA"}
DELIVERED_STATUSES = {"DELIVERED", "ENTREGUE"}


class DriverLoginPayload(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


class DriverLocationPayload(BaseModel):
    order_id: int
    lat: float
    lng: float


def _normalize_workflow_status(value: str | None) -> str:
    status_value = (value or "").upper()
    if status_value in READY_FOR_DELIVERY_STATUSES:
        return "READY_FOR_DELIVERY"
    if status_value in DRIVER_ASSIGNED_STATUSES:
        return "DRIVER_ASSIGNED"
    if status_value in OUT_FOR_DELIVERY_STATUSES:
        return "OUT_FOR_DELIVERY"
    if status_value in DELIVERED_STATUSES:
        return "DELIVERED"
    return status_value or "CREATED"


def _serialize_order(order: Order) -> dict[str, Any]:
    return {
        "id": int(order.id),
        "daily_order_number": order.daily_order_number,
        "status": _normalize_workflow_status(order.status),
        "raw_status": order.status,
        "customer_name": order.customer_name or order.cliente_nome,
        "address": order.endereco,
        "delivery_lat": float(order.delivery_lat) if order.delivery_lat is not None else None,
        "delivery_lng": float(order.delivery_lng) if order.delivery_lng is not None else None,
        "customer_lat": float(order.customer_lat) if order.customer_lat is not None else (float(order.delivery_lat) if order.delivery_lat is not None else None),
        "customer_lng": float(order.customer_lng) if order.customer_lng is not None else (float(order.delivery_lng) if order.delivery_lng is not None else None),
        "created_at": order.created_at.isoformat() if order.created_at else None,
    }


@router.post("/auth/login")
def driver_login(payload: DriverLoginPayload, request: Request, db: Session = Depends(get_db)):
    tenant = getattr(request.state, "tenant", None)
    if tenant is None:
        raise HTTPException(status_code=400, detail="Tenant não resolvido")

    driver = (
        db.query(AdminUser)
        .filter(
            AdminUser.tenant_id == int(tenant.id),
            func.upper(AdminUser.role) == "DELIVERY",
            AdminUser.active.is_(True),
            func.lower(AdminUser.email) == payload.email.lower(),
        )
        .first()
    )
    if driver is None or not verify_password(payload.password, driver.password_hash):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    token = create_access_token(
        str(driver.id),
        extra={
            "driver_id": int(driver.id),
            "delivery_user_id": int(driver.id),
            "restaurant_id": int(driver.tenant_id),
            "tenant_id": int(driver.tenant_id),
            "role": "driver",
        },
    )

    return {
        "token": token,
        "driver": {
            "id": int(driver.id),
            "name": driver.name,
            "email": driver.email,
            "restaurant_id": int(driver.tenant_id),
            "role": "driver",
        },
    }


@router.get("/state")
def get_driver_state(
    db: Session = Depends(get_db),
    current_driver: AdminUser = Depends(get_current_delivery_user),
):
    tenant_id = int(current_driver.tenant_id)
    driver_id = int(current_driver.id)

    active_delivery = (
        db.query(Order)
        .filter(
            Order.tenant_id == tenant_id,
            Order.assigned_delivery_user_id == driver_id,
            func.upper(Order.status).in_(DRIVER_ASSIGNED_STATUSES | OUT_FOR_DELIVERY_STATUSES),
        )
        .order_by(desc(Order.created_at), desc(Order.id))
        .first()
    )

    available_orders = (
        db.query(Order)
        .filter(
            Order.tenant_id == tenant_id,
            func.upper(Order.status).in_(READY_FOR_DELIVERY_STATUSES),
            Order.assigned_delivery_user_id.is_(None),
        )
        .order_by(desc(Order.created_at), desc(Order.id))
        .all()
    )

    return {
        "driver": {
            "id": driver_id,
            "name": current_driver.name,
            "email": current_driver.email,
            "restaurant_id": tenant_id,
            "role": "driver",
        },
        "active_delivery": _serialize_order(active_delivery) if active_delivery else None,
        "available_orders": [_serialize_order(order) for order in available_orders],
    }


@router.post("/orders/{order_id}/accept")
def accept_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_driver: AdminUser = Depends(get_current_delivery_user),
):
    tenant_id = int(current_driver.tenant_id)
    order = db.query(Order).filter(Order.id == order_id, Order.tenant_id == tenant_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")

    if order.assigned_delivery_user_id and int(order.assigned_delivery_user_id) != int(current_driver.id):
        raise HTTPException(status_code=409, detail="Pedido já aceito por outro motorista")

    if (order.status or "").upper() not in READY_FOR_DELIVERY_STATUSES | DRIVER_ASSIGNED_STATUSES:
        raise HTTPException(status_code=409, detail="Pedido não está disponível para aceite")

    previous = order.status
    order.assigned_delivery_user_id = int(current_driver.id)
    order.status = "DRIVER_ASSIGNED"
    db.commit()
    emit_order_status_changed(order, previous)
    return {"ok": True, "status": "DRIVER_ASSIGNED", "order_id": order.id}


@router.post("/orders/{order_id}/start")
def start_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_driver: AdminUser = Depends(get_current_delivery_user),
):
    tenant_id = int(current_driver.tenant_id)
    order = db.query(Order).filter(Order.id == order_id, Order.tenant_id == tenant_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    if int(order.assigned_delivery_user_id or 0) != int(current_driver.id):
        raise HTTPException(status_code=409, detail="Pedido precisa ser aceito por este motorista")

    current = (order.status or "").upper()
    if current in DELIVERED_STATUSES:
        raise HTTPException(status_code=409, detail="Pedido já entregue")
    if current not in DRIVER_ASSIGNED_STATUSES | OUT_FOR_DELIVERY_STATUSES:
        raise HTTPException(status_code=409, detail="Pedido precisa estar em DRIVER_ASSIGNED")

    previous = order.status
    order.status = "OUT_FOR_DELIVERY"
    if not order.start_delivery_at:
        order.start_delivery_at = datetime.now(timezone.utc)
    db.commit()
    emit_order_status_changed(order, previous)
    return {"ok": True, "status": "OUT_FOR_DELIVERY", "order_id": order.id}


@router.post("/orders/{order_id}/complete")
def complete_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_driver: AdminUser = Depends(get_current_delivery_user),
):
    tenant_id = int(current_driver.tenant_id)
    order = db.query(Order).filter(Order.id == order_id, Order.tenant_id == tenant_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    if int(order.assigned_delivery_user_id or 0) != int(current_driver.id):
        raise HTTPException(status_code=409, detail="Pedido atribuído para outro motorista")

    previous = order.status
    order.status = "DELIVERED"
    db.commit()
    emit_order_status_changed(order, previous)
    return {"ok": True, "status": "DELIVERED", "order_id": order.id}


@router.post("/location")
def update_location(
    payload: DriverLocationPayload,
    db: Session = Depends(get_db),
    current_driver: AdminUser = Depends(get_current_delivery_user),
):
    tenant_id = int(current_driver.tenant_id)
    driver_id = int(current_driver.id)
    logger.info(
        "driver location update request driver_id=%s tenant_id=%s order_id=%s lat=%s lng=%s",
        driver_id,
        tenant_id,
        payload.order_id,
        payload.lat,
        payload.lng,
    )

    try:
        order = db.query(Order).filter(Order.id == payload.order_id, Order.tenant_id == tenant_id).first()
        if order is None:
            logger.warning(
                "driver location order not found driver_id=%s tenant_id=%s order_id=%s",
                driver_id,
                tenant_id,
                payload.order_id,
            )
            raise HTTPException(status_code=404, detail="Pedido não encontrado")

        logger.info(
            "driver location resolved order_id=%s status=%s restaurant_id=%s assigned_driver_id=%s",
            int(order.id),
            order.status,
            int(order.tenant_id),
            order.assigned_delivery_user_id,
        )

        if int(order.assigned_delivery_user_id or 0) != driver_id:
            raise HTTPException(status_code=409, detail="Pedido atribuído para outro motorista")

        tracking = db.query(DeliveryTracking).filter(DeliveryTracking.order_id == int(order.id)).first()
        if tracking is None:
            tracking = DeliveryTracking(
                order_id=int(order.id),
                delivery_user_id=driver_id,
                estimated_duration_seconds=0,
                expected_delivery_at=datetime.now(timezone.utc),
            )
            db.add(tracking)

        tracking.current_lat = payload.lat
        tracking.current_lng = payload.lng
        tracking.delivery_user_id = driver_id
        db.commit()

        publish_delivery_driver_location_event(
            tenant_id=tenant_id,
            driver_id=driver_id,
            order_id=int(order.id),
            lat=payload.lat,
            lng=payload.lng,
        )

        return {"ok": True}
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception(
            "driver location update failed driver_id=%s tenant_id=%s order_id=%s",
            driver_id,
            tenant_id,
            payload.order_id,
        )
        raise HTTPException(status_code=500, detail="Falha ao atualizar localização")


@router.get("/live-map/{order_id}")
def get_live_map(
    order_id: int,
    db: Session = Depends(get_db),
    current_driver: AdminUser = Depends(get_current_delivery_user),
):
    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.tenant_id == int(current_driver.tenant_id))
        .first()
    )
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado")

    tracking = (
        db.query(DeliveryTracking)
        .filter(DeliveryTracking.order_id == int(order_id))
        .order_by(desc(DeliveryTracking.created_at), desc(DeliveryTracking.id))
        .first()
    )
    if tracking is None:
        return {"order_id": int(order_id), "driver_location": None}

    return {
        "order_id": int(order_id),
        "driver_location": {
            "lat": tracking.current_lat,
            "lng": tracking.current_lng,
            "updated_at": tracking.created_at.isoformat() if tracking.created_at else None,
        },
    }
