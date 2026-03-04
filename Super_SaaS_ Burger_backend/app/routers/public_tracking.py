from __future__ import annotations

from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException, WebSocket
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from app.core.database import SessionLocal, get_db
from app.models.admin_user import AdminUser
from app.integrations.redis_client import get_async_redis_client
from app.models.delivery_log import DeliveryLog
from app.models.order import Order
from app.realtime.delivery_envelope import parse_delivery_envelope
from app.realtime.publisher import order_tracking_channel
from app.services.public_tracking import is_tracking_token_active

router = APIRouter(tags=["public-tracking"])


class TrackingNotFound(Exception):
    pass


def _parse_tracking_token(raw_token: str) -> str:
    try:
        return str(uuid.UUID(str(raw_token).strip()))
    except Exception as exc:
        raise TrackingNotFound() from exc


def _resolve_public_tracking_order(db: Session, tracking_token: str) -> Order:
    token = _parse_tracking_token(tracking_token)
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


@router.get("/api/public/track/{tracking_token}")
def get_public_tracking(tracking_token: str, db: Session = Depends(get_db)):
    try:
        order = _resolve_public_tracking_order(db, tracking_token)
    except TrackingNotFound as exc:
        raise HTTPException(status_code=404, detail="Rastreamento não encontrado") from exc

    return _build_public_tracking_snapshot(db, order)


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
