from __future__ import annotations

from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException, WebSocket
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from app.core.database import SessionLocal, get_db
from app.models.admin_user import AdminUser
from app.integrations.redis_client import get_async_redis_client
from app.models.delivery_log import DeliveryLog
from app.models.order_item import OrderItem
from app.models.order import Order
from app.models.tenant import Tenant
from app.realtime.delivery_envelope import parse_delivery_envelope
from app.realtime.publisher import order_tracking_channel
from app.services.public_tracking import is_tracking_token_active

router = APIRouter(tags=["public-tracking"])

NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}

STATUS_LABELS = {
    "PENDING": {"label": "Aguardando cozinha", "step": 1},
    "RECEBIDO": {"label": "Aguardando cozinha", "step": 1},
    "PREPARING": {"label": "Em preparo", "step": 2},
    "EM_PREPARO": {"label": "Em preparo", "step": 2},
    "READY": {"label": "Pronto", "step": 3},
    "PRONTO": {"label": "Pronto", "step": 3},
    "OUT_FOR_DELIVERY": {"label": "Saiu para entrega", "step": 4},
    "SAIU": {"label": "Saiu para entrega", "step": 4},
    "SAIU_PARA_ENTREGA": {"label": "Saiu para entrega", "step": 4},
    "DELIVERED": {"label": "Entregue", "step": 5},
    "ENTREGUE": {"label": "Entregue", "step": 5},
}


class TrackingNotFound(Exception):
    pass


def _parse_tracking_token(raw_token: str) -> str:
    try:
        return str(uuid.UUID(str(raw_token).strip()))
    except Exception as exc:
        raise TrackingNotFound() from exc


def _resolve_public_tracking_order(db: Session, tracking_token: str) -> Order:
    token = _parse_tracking_token(tracking_token)
    db.expire_all()
    order = db.query(Order).filter(Order.tracking_token == token).first()
    if not order:
        raise TrackingNotFound()

    if not is_tracking_token_active(
        tracking_expires_at=order.tracking_expires_at,
        tracking_revoked=bool(order.tracking_revoked),
        now=datetime.now(timezone.utc),
    ):
        raise TrackingNotFound()

    return order


def _build_public_tracking_snapshot(db: Session, order: Order) -> dict:
    delivery_user_name = None
    if order.assigned_delivery_user_id:
        delivery_user = (
            db.query(AdminUser)
            .filter(
                AdminUser.id == int(order.assigned_delivery_user_id),
                AdminUser.tenant_id == int(order.tenant_id),
                AdminUser.active.is_(True),
                AdminUser.role == "DELIVERY",
            )
            .first()
        )
        if delivery_user:
            delivery_user_name = delivery_user.name

    last_location = (
        db.query(DeliveryLog)
        .filter(
            DeliveryLog.tenant_id == int(order.tenant_id),
            DeliveryLog.order_id == int(order.id),
            DeliveryLog.event_type == "location_update",
        )
        .order_by(DeliveryLog.created_at.desc(), DeliveryLog.id.desc())
        .first()
    )

    return {
        "status": order.status,
        "delivery_user": {"name": delivery_user_name} if delivery_user_name else None,
        "last_location": {
            "lat": float(last_location.latitude),
            "lng": float(last_location.longitude),
        }
        if last_location and last_location.latitude is not None and last_location.longitude is not None
        else None,
    }


def _resolve_tracking_metadata(order: Order) -> dict:
    status_key = str(order.status or "").strip().upper()
    status_meta = STATUS_LABELS.get(status_key, {"label": str(order.status or "Pedido recebido"), "step": 1})
    estimated_minutes = None
    if getattr(order, "estimated_delivery_minutes", None) is not None:
        try:
            estimated_minutes = int(order.estimated_delivery_minutes)
        except (TypeError, ValueError):
            estimated_minutes = None
    return {
        "status_label": status_meta["label"],
        "status_step": status_meta["step"],
        "estimated_minutes": estimated_minutes,
    }


def _resolve_order_type_label(order: Order) -> str:
    value = str(getattr(order, "delivery_type", None) or getattr(order, "order_type", None) or "").strip().upper()
    if value in {"ENTREGA", "DELIVERY"}:
        return "ENTREGA"
    if value in {"RETIRADA", "PICKUP"}:
        return "RETIRADA"
    if value in {"MESA", "TABLE"}:
        return "MESA"
    return value or "ENTREGA"


def _build_public_order_payload(db: Session, order: Order) -> dict:
    items = (
        db.query(OrderItem)
        .filter(OrderItem.order_id == int(order.id))
        .order_by(OrderItem.id.asc())
        .all()
    )
    tenant = db.query(Tenant).filter(Tenant.id == int(order.tenant_id)).first()
    metadata = _resolve_tracking_metadata(order)

    return {
        "order_number": int(order.daily_order_number or order.id),
        "status": order.status,
        "status_label": metadata["status_label"],
        "status_step": metadata["status_step"],
        "order_type": _resolve_order_type_label(order),
        "items": [{"name": str(item.name or ""), "quantity": int(item.quantity or 0)} for item in items],
        "total": float(order.total_cents or order.valor_total or 0),
        "payment_method": order.payment_method,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "ready_at": order.ready_at.isoformat() if order.ready_at else None,
        "start_delivery_at": order.start_delivery_at.isoformat() if order.start_delivery_at else None,
        "estimated_minutes": metadata["estimated_minutes"],
        "store_name": getattr(tenant, "business_name", None),
        "store_logo_url": getattr(tenant, "logo_url", None),
        "primary_color": getattr(tenant, "primary_color", None),
    }


@router.get("/api/public/track/{tracking_token}")
def get_public_tracking(tracking_token: str, db: Session = Depends(get_db)):
    try:
        order = _resolve_public_tracking_order(db, tracking_token)
    except TrackingNotFound as exc:
        raise HTTPException(status_code=404, detail="Rastreamento não encontrado") from exc

    return JSONResponse(
        content=_build_public_tracking_snapshot(db, order),
        headers=NO_CACHE_HEADERS,
    )


@router.get("/api/public/order/{tracking_token}")
def get_public_order_tracking(tracking_token: str, db: Session = Depends(get_db)):
    try:
        order = _resolve_public_tracking_order(db, tracking_token)
    except TrackingNotFound as exc:
        raise HTTPException(status_code=404, detail="Pedido não encontrado") from exc

    return JSONResponse(
        content=_build_public_order_payload(db, order),
        headers=NO_CACHE_HEADERS,
    )


@router.websocket("/ws/public/tracking/{tracking_token}")
async def ws_public_tracking(websocket: WebSocket, tracking_token: str):
    db = SessionLocal()
    try:
        order = _resolve_public_tracking_order(db, tracking_token)
    except TrackingNotFound:
        db.close()
        await websocket.close(code=1008, reason="Token inválido")
        return

    tenant_id = int(order.tenant_id)
    tracking_channel = order_tracking_channel(tenant_id, int(order.id))
    initial_payload = _build_public_tracking_snapshot(db, order)
    db.close()

    await websocket.accept()
    await websocket.send_json(initial_payload)

    redis = get_async_redis_client()
    if redis is None:
        await websocket.close(code=1011, reason="Redis indisponível")
        return

    pubsub = redis.pubsub()
    try:
        await pubsub.subscribe(tracking_channel)
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message is None:
                continue

            raw_payload = message.get("data")
            payload_text = raw_payload.decode() if isinstance(raw_payload, bytes) else str(raw_payload)
            payload_data = parse_delivery_envelope(payload_text, expected_tenant_id=tenant_id)
            if payload_data is None:
                continue

            await websocket.send_json(payload_data)
    except WebSocketDisconnect:
        return
    finally:
        await pubsub.aclose()
        await redis.aclose()
