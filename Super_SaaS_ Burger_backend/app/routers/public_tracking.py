from __future__ import annotations

from datetime import datetime, timezone
import asyncio
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

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
from app.services.gps_service import calculate_distance_km, estimate_eta_seconds
from app.modules.tracking.service import get_delivery_location, get_delivery_total_distance

router = APIRouter(tags=["public-tracking"])

NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}

STATUS_NORMALIZE = {
    "RECEBIDO": "pending",
    "recebido": "pending",
    "pending": "pending",
    "EM_PREPARO": "preparing",
    "em_preparo": "preparing",
    "preparing": "preparing",
    "PRONTO": "ready",
    "pronto": "ready",
    "ready": "ready",
    "SAIU": "delivering",
    "OUT_FOR_DELIVERY": "delivering",
    "out_for_delivery": "delivering",
    "SAIU_PARA_ENTREGA": "delivering",
    "saiu_para_entrega": "delivering",
    "delivering": "delivering",
    "DELIVERED": "delivered",
    "delivered": "delivered",
    "ENTREGUE": "delivered",
    "entregue": "delivered",
}

STATUS_STEP = {
    "pending": 1,
    "preparing": 2,
    "ready": 3,
    "delivering": 4,
    "delivered": 5,
}

STATUS_LABEL = {
    "pending": "Aguardando cozinha",
    "preparing": "Em preparo",
    "ready": "Pronto",
    "delivering": "Saiu para entrega",
    "delivered": "Entregue",
}


class TrackingNotFound(Exception):
    pass


def _resolve_destination_coordinates(order: Order) -> tuple[float | None, float | None]:
    for lat_value, lng_value in (
        (getattr(order, "destination_lat", None), getattr(order, "destination_lng", None)),
        (getattr(order, "customer_lat", None), getattr(order, "customer_lng", None)),
        (getattr(order, "delivery_lat", None), getattr(order, "delivery_lng", None)),
    ):
        if lat_value is None or lng_value is None:
            continue
        try:
            return float(lat_value), float(lng_value)
        except (TypeError, ValueError):
            continue
    return None, None


def _clamp_progress(progress: float) -> float:
    return max(0.0, min(1.0, progress))


def _build_live_progress_payload(order: Order, driver_location: dict | None, total_distance_km: float | None) -> dict[str, object]:
    destination_lat, destination_lng = _resolve_destination_coordinates(order)
    if driver_location is None or destination_lat is None or destination_lng is None:
        return {"progress": 0.0, "distance_km": None, "eta_seconds": None, "last_location": driver_location}

    try:
        driver_lat = float(driver_location.get("lat"))
        driver_lng = float(driver_location.get("lng"))
    except (TypeError, ValueError):
        return {"progress": 0.0, "distance_km": None, "eta_seconds": None, "last_location": None}

    current_distance_km = max(0.0, calculate_distance_km(driver_lat, driver_lng, destination_lat, destination_lng))
    safe_total_distance = max(float(total_distance_km or 0.0), current_distance_km, 0.001)
    progress = _clamp_progress(1 - (current_distance_km / safe_total_distance))

    return {
        "progress": progress,
        "distance_km": round(current_distance_km, 3),
        "eta_seconds": estimate_eta_seconds(current_distance_km),
        "last_location": {
            "lat": driver_lat,
            "lng": driver_lng,
            "updated_at": driver_location.get("updated_at"),
        },
    }


def _parse_tracking_token(raw_token: str) -> str:
    try:
        return str(uuid.UUID(str(raw_token).strip()))
    except Exception as exc:
        raise TrackingNotFound() from exc


def _resolve_public_tracking_order(db: Session, tracking_token: str) -> Order:
    token = _parse_tracking_token(tracking_token)
    if hasattr(db, "expire_all"):
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


async def _build_public_tracking_snapshot(db: Session, order: Order) -> dict:
    raw_status, normalized_status, status_step, status_label = _resolve_tracking_metadata(order)

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

    redis = get_async_redis_client()
    try:
        live_location = await get_delivery_location(redis, int(order.id))
        total_distance_km = await get_delivery_total_distance(redis, int(order.id))
    finally:
        if redis is not None:
            await redis.aclose()

    live_progress = _build_live_progress_payload(order, live_location, total_distance_km)

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

    fallback_last_location = {
        "lat": float(last_location.latitude),
        "lng": float(last_location.longitude),
    } if last_location and last_location.latitude is not None and last_location.longitude is not None else None

    return {
        "status": normalized_status,
        "status_raw": raw_status,
        "status_step": status_step,
        "status_label": status_label,
        "delivery_user": {"name": delivery_user_name} if delivery_user_name else None,
        "progress": live_progress["progress"],
        "distance_km": live_progress["distance_km"],
        "eta_seconds": live_progress["eta_seconds"],
        "last_location": live_progress["last_location"] or fallback_last_location,
    }


def _resolve_tracking_metadata(order: Order) -> tuple[str, str, int, str]:
    raw_status = str(order.status or "RECEBIDO").strip() or "RECEBIDO"
    normalized_status = STATUS_NORMALIZE.get(
        raw_status,
        STATUS_NORMALIZE.get(raw_status.upper(), "pending"),
    )
    status_step = STATUS_STEP.get(normalized_status, 1)
    status_label = STATUS_LABEL.get(normalized_status, "Aguardando cozinha")

    return raw_status, normalized_status, status_step, status_label




def _build_public_tracking_event(message: dict) -> dict | None:
    payload = message.get("payload") if isinstance(message.get("payload"), dict) else message

    status = payload.get("status_raw") or payload.get("status")
    normalized_status = STATUS_NORMALIZE.get(
        str(status or "").strip(),
        STATUS_NORMALIZE.get(str(status or "").strip().upper(), None),
    )
    status_step = STATUS_STEP.get(normalized_status, None) if normalized_status else None

    lat = payload.get("lat")
    lng = payload.get("lng")
    last_location = payload.get("last_location")
    if isinstance(last_location, dict):
        lat = last_location.get("lat", lat)
        lng = last_location.get("lng", lng)

    normalized_payload: dict[str, object] = {}
    if normalized_status:
        normalized_payload["status"] = normalized_status
        normalized_payload["status_raw"] = str(status)
        normalized_payload["status_step"] = int(payload.get("status_step") or status_step or 0)

    for field_name in ("progress", "distance_km", "eta_seconds", "order_id"):
        if payload.get(field_name) is not None:
            normalized_payload[field_name] = payload.get(field_name)

    if lat is not None and lng is not None:
        try:
            normalized_payload["last_location"] = {"lat": float(lat), "lng": float(lng)}
        except (TypeError, ValueError):
            pass

    if not normalized_payload:
        return None

    return normalized_payload

def _resolve_estimated_minutes(order: Order) -> int | None:
    estimated_minutes = None
    if getattr(order, "estimated_delivery_minutes", None) is not None:
        try:
            estimated_minutes = int(order.estimated_delivery_minutes)
        except (TypeError, ValueError):
            estimated_minutes = None
    return estimated_minutes


def _resolve_order_type_label(order: Order) -> str:
    value = str(getattr(order, "delivery_type", None) or getattr(order, "order_type", None) or "").strip().upper()
    if value in {"ENTREGA", "DELIVERY"}:
        return "ENTREGA"
    if value in {"RETIRADA", "PICKUP"}:
        return "RETIRADA"
    if value in {"MESA", "TABLE"}:
        return "MESA"
    return value or "ENTREGA"


async def _build_public_order_payload(db: Session, order: Order) -> dict:
    items = (
        db.query(OrderItem)
        .filter(OrderItem.order_id == int(order.id))
        .order_by(OrderItem.id.asc())
        .all()
    )
    tenant = db.query(Tenant).filter(Tenant.id == int(order.tenant_id)).first()
    raw_status, normalized_status, status_step, status_label = _resolve_tracking_metadata(order)
    estimated_minutes = _resolve_estimated_minutes(order)
    redis = get_async_redis_client()
    try:
        live_location = await get_delivery_location(redis, int(order.id))
        total_distance_km = await get_delivery_total_distance(redis, int(order.id))
    finally:
        if redis is not None:
            await redis.aclose()
    live_progress = _build_live_progress_payload(order, live_location, total_distance_km)

    return {
        "order_number": int(order.daily_order_number or order.id),
        "status": normalized_status,
        "status_raw": raw_status,
        "status_label": status_label,
        "status_step": status_step,
        "order_type": _resolve_order_type_label(order),
        "items": [{"name": str(item.name or ""), "quantity": int(item.quantity or 0)} for item in items],
        "total": float(order.total_cents or order.valor_total or 0),
        "payment_method": order.payment_method,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "ready_at": order.ready_at.isoformat() if order.ready_at else None,
        "start_delivery_at": order.start_delivery_at.isoformat() if order.start_delivery_at else None,
        "estimated_minutes": estimated_minutes,
        "progress": live_progress["progress"],
        "distance_km": live_progress["distance_km"],
        "eta_seconds": live_progress["eta_seconds"],
        "last_location": live_progress["last_location"],
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
        content=asyncio.run(_build_public_tracking_snapshot(db, order)),
        headers=NO_CACHE_HEADERS,
    )


@router.get("/api/public/order/{tracking_token}")
def get_public_order_tracking(tracking_token: str, db: Session = Depends(get_db)):
    try:
        order = _resolve_public_tracking_order(db, tracking_token)
    except TrackingNotFound as exc:
        raise HTTPException(status_code=404, detail="Pedido não encontrado") from exc

    return JSONResponse(
        content=asyncio.run(_build_public_order_payload(db, order)),
        headers=NO_CACHE_HEADERS,
    )




@router.get("/api/public/sse/{tracking_token}")
async def sse_public_tracking(tracking_token: str, request: Request):
    db = SessionLocal()
    try:
        order = _resolve_public_tracking_order(db, tracking_token)
        tenant_id = int(order.tenant_id)
        order_id = int(order.id)
        initial_payload = await _build_public_tracking_snapshot(db, order)
    except TrackingNotFound as exc:
        raise HTTPException(status_code=404, detail="Rastreamento não encontrado") from exc
    finally:
        db.close()

    async def event_generator():
        yield f"data: {json.dumps(initial_payload)}\n\n"

        redis = get_async_redis_client()
        pubsub = redis.pubsub() if redis is not None else None
        last_progress_payload = {
            "progress": initial_payload.get("progress"),
            "distance_km": initial_payload.get("distance_km"),
            "eta_seconds": initial_payload.get("eta_seconds"),
            "last_location": initial_payload.get("last_location"),
        }
        try:
            if pubsub is not None:
                await pubsub.subscribe(order_tracking_channel(tenant_id, order_id))
            while True:
                if await request.is_disconnected():
                    break

                if redis is not None:
                    live_location = await get_delivery_location(redis, order_id)
                    total_distance_km = await get_delivery_total_distance(redis, order_id)
                    live_progress = _build_live_progress_payload(order, live_location, total_distance_km)
                    current_progress_payload = {
                        "order_id": order_id,
                        "status": "OUT_FOR_DELIVERY",
                        "progress": live_progress["progress"],
                        "distance_km": live_progress["distance_km"],
                        "eta_seconds": live_progress["eta_seconds"],
                        "last_location": live_progress["last_location"],
                    }
                    if current_progress_payload != last_progress_payload and current_progress_payload["last_location"] is not None:
                        last_progress_payload = current_progress_payload.copy()
                        yield f"data: {json.dumps(current_progress_payload)}\n\n"

                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0) if pubsub is not None else None
                if message is not None:
                    raw_payload = message.get("data")
                    payload_text = raw_payload.decode() if isinstance(raw_payload, bytes) else str(raw_payload)
                    payload_data = parse_delivery_envelope(payload_text, expected_tenant_id=tenant_id)
                    if payload_data is not None:
                        normalized_payload = _build_public_tracking_event(payload_data)
                        if normalized_payload is not None:
                            yield f"data: {json.dumps(normalized_payload)}\n\n"
                            continue

                yield ": keep-alive\n\n"
                await asyncio.sleep(1)
        finally:
            if pubsub is not None:
                await pubsub.aclose()
            if redis is not None:
                await redis.aclose()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            **NO_CACHE_HEADERS,
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

@router.get("/api/orders/by-token/{tracking_token}", include_in_schema=False)
def get_order_by_tracking_token(tracking_token: str, db: Session = Depends(get_db)):
    try:
        order = _resolve_public_tracking_order(db, tracking_token)
    except TrackingNotFound as exc:
        raise HTTPException(status_code=404, detail="Pedido não encontrado") from exc

    return JSONResponse(
        content={
            "id": int(order.id),
            "status": str(order.status or ""),
        },
        headers=NO_CACHE_HEADERS,
    )

