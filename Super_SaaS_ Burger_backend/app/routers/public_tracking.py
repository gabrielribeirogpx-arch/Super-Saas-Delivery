from __future__ import annotations

from datetime import datetime, timezone
import asyncio
import json
import logging
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
from app.models.tenant_public_settings import TenantPublicSettings
from app.realtime.delivery_envelope import parse_delivery_envelope
from app.realtime.publisher import order_tracking_channel
from app.services.directions_service import get_route_data
from app.services.public_tracking import default_tracking_expires_at, is_tracking_token_active, normalize_tracking_token
from app.services.gps_service import calculate_distance_km, estimate_eta_seconds
from app.models.delivery_tracking import DeliveryTracking
from app.modules.tracking.service import get_delivery_location

router = APIRouter(tags=["public-tracking"])
logger = logging.getLogger(__name__)

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


def _resolve_tracking_record(db: Session, order: Order) -> DeliveryTracking | None:
    return (
        db.query(DeliveryTracking)
        .filter(DeliveryTracking.order_id == int(order.id))
        .order_by(DeliveryTracking.created_at.desc(), DeliveryTracking.id.desc())
        .first()
    )


async def _resolve_live_driver_state(
    order: Order,
    tracking: DeliveryTracking | None,
) -> tuple[float | None, float | None, str | None]:
    driver_lat = getattr(tracking, "current_lat", None) if tracking is not None else None
    driver_lng = getattr(tracking, "current_lng", None) if tracking is not None else None
    updated_at = getattr(tracking, "created_at", None) if tracking is not None else None

    redis = get_async_redis_client()
    if redis is not None:
        live_location = await get_delivery_location(redis, int(order.id))
        if isinstance(live_location, dict):
            live_lat = live_location.get("lat")
            live_lng = live_location.get("lng")
            if live_lat is not None and live_lng is not None:
                try:
                    driver_lat = float(live_lat)
                    driver_lng = float(live_lng)
                    updated_at = live_location.get("updated_at") or updated_at
                except (TypeError, ValueError):
                    pass

    normalized_updated_at = updated_at.isoformat() if hasattr(updated_at, "isoformat") else updated_at
    return driver_lat, driver_lng, normalized_updated_at


async def _resolve_route_metrics(
    driver_lat: float | None,
    driver_lng: float | None,
    destination_lat: float | None,
    destination_lng: float | None,
) -> tuple[int | None, int | None]:
    if (
        driver_lat is None
        or driver_lng is None
        or destination_lat is None
        or destination_lng is None
    ):
        return None, None

    distance_from_directions, duration_from_directions, _geometry = await get_route_data(
        driver_lat,
        driver_lng,
        destination_lat,
        destination_lng,
    )
    if distance_from_directions is not None and duration_from_directions is not None:
        return max(0, int(distance_from_directions)), max(0, int(duration_from_directions))

    fallback_distance_meters = max(0, int(calculate_distance_km(
        driver_lat,
        driver_lng,
        destination_lat,
        destination_lng,
    ) * 1000))
    fallback_duration_seconds = max(0, int(estimate_eta_seconds(fallback_distance_meters / 1000, avg_speed_kmh=30)))
    return fallback_distance_meters, fallback_duration_seconds


async def _build_live_progress_payload(order: Order, tracking: DeliveryTracking | None) -> dict[str, object]:
    destination_lat, destination_lng = _resolve_destination_coordinates(order)

    if tracking is None:
        return {
            "progress": 0.0,
            "distance_meters": None,
            "duration_seconds": None,
            "last_location": None,
            "driver_lat": None,
            "driver_lng": None,
            "destination_lat": destination_lat,
            "destination_lng": destination_lng,
            "initial_distance_meters": None,
        }

    driver_lat, driver_lng, updated_at = await _resolve_live_driver_state(order, tracking)
    route_distance_meters = getattr(tracking, "route_distance_meters", None)
    route_duration_seconds = getattr(tracking, "route_duration_seconds", None)
    estimated_duration_seconds = getattr(tracking, "estimated_duration_seconds", None)
    started_at_distance = getattr(tracking, "route_distance_meters", None)

    current_distance_meters, duration_seconds = await _resolve_route_metrics(
        driver_lat,
        driver_lng,
        destination_lat,
        destination_lng,
    )

    if current_distance_meters is None:
        try:
            current_distance_meters = max(0, int(route_distance_meters)) if route_distance_meters is not None else None
        except (TypeError, ValueError):
            current_distance_meters = None

    if duration_seconds is None:
        try:
            duration_seconds = max(0, int(route_duration_seconds)) if route_duration_seconds is not None else None
        except (TypeError, ValueError):
            duration_seconds = None

    try:
        initial_distance_meters = max(0, int(started_at_distance)) if started_at_distance is not None else None
    except (TypeError, ValueError):
        initial_distance_meters = None

    if initial_distance_meters is None:
        try:
            initial_distance_meters = max(0, int(estimated_duration_seconds) * 833 // 100) if estimated_duration_seconds is not None else None
        except (TypeError, ValueError):
            initial_distance_meters = None

    if initial_distance_meters is None and current_distance_meters is not None:
        initial_distance_meters = current_distance_meters

    if initial_distance_meters is None or current_distance_meters is None:
        progress = 0.0
    else:
        progress = _clamp_progress(1 - (current_distance_meters / max(initial_distance_meters, 1)))

    return {
        "progress": progress,
        "distance_meters": current_distance_meters,
        "duration_seconds": duration_seconds,
        "last_location": {
            "lat": float(driver_lat),
            "lng": float(driver_lng),
            "updated_at": updated_at,
        } if driver_lat is not None and driver_lng is not None else None,
        "driver_lat": float(driver_lat) if driver_lat is not None else None,
        "driver_lng": float(driver_lng) if driver_lng is not None else None,
        "destination_lat": destination_lat,
        "destination_lng": destination_lng,
        "initial_distance_meters": initial_distance_meters,
    }


def _parse_tracking_token(raw_token: str) -> str:
    try:
        return normalize_tracking_token(raw_token)
    except ValueError as exc:
        raise TrackingNotFound() from exc


def _resolve_public_tracking_order(db: Session, tracking_token: str, request: Request | None = None) -> Order:
    token = _parse_tracking_token(tracking_token)

    if hasattr(db, "expire_all"):
        db.expire_all()

    order = db.query(Order).filter(Order.tracking_token == token).first()
    if not order:
        raise TrackingNotFound()

    tracking_expires_at = getattr(order, "tracking_expires_at", None)
    tracking_revoked = bool(getattr(order, "tracking_revoked", False))

    if tracking_expires_at is None and not tracking_revoked:
        tracking_expires_at = default_tracking_expires_at()
        setattr(order, "tracking_expires_at", tracking_expires_at)
        if hasattr(db, "add"):
            db.add(order)
        if hasattr(db, "commit"):
            db.commit()
        if hasattr(db, "refresh"):
            db.refresh(order)

    if request is not None:
        request.state.tenant_id = int(order.tenant_id)

    logger.info(
        "public_tracking_lookup tracking_token=%s order_id=%s tenant_id=%s",
        token,
        int(order.id),
        int(order.tenant_id),
    )

    if not is_tracking_token_active(
        tracking_expires_at=tracking_expires_at,
        tracking_revoked=tracking_revoked,
        now=datetime.now(timezone.utc),
    ):
        raise TrackingNotFound()

    return order


async def _load_live_progress_snapshot_async(db: Session, order: Order) -> dict[str, object]:
    tracking = _resolve_tracking_record(db, order)
    return await _build_live_progress_payload(order, tracking)


def _load_live_progress_snapshot(db: Session, order: Order) -> dict[str, object]:
    try:
        return asyncio.run(_load_live_progress_snapshot_async(db, order))
    except RuntimeError:
        tracking = _resolve_tracking_record(db, order)
        return {
            "progress": 0.0,
            "distance_meters": getattr(tracking, "route_distance_meters", None) if tracking is not None else None,
            "duration_seconds": getattr(tracking, "route_duration_seconds", None) if tracking is not None else None,
            "last_location": {
                "lat": float(tracking.current_lat),
                "lng": float(tracking.current_lng),
                "updated_at": tracking.created_at.isoformat() if getattr(tracking, "created_at", None) else None,
            } if tracking is not None and tracking.current_lat is not None and tracking.current_lng is not None else None,
            "driver_lat": float(tracking.current_lat) if tracking is not None and tracking.current_lat is not None else None,
            "driver_lng": float(tracking.current_lng) if tracking is not None and tracking.current_lng is not None else None,
            "destination_lat": _resolve_destination_coordinates(order)[0],
            "destination_lng": _resolve_destination_coordinates(order)[1],
            "initial_distance_meters": getattr(tracking, "route_distance_meters", None) if tracking is not None else None,
        }


def _build_public_tracking_snapshot(db: Session, order: Order) -> dict:
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

    live_progress = _load_live_progress_snapshot(db, order)

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
        "distance_meters": live_progress["distance_meters"],
        "duration_seconds": live_progress["duration_seconds"],
        "driver_lat": live_progress["driver_lat"],
        "driver_lng": live_progress["driver_lng"],
        "destination_lat": live_progress["destination_lat"],
        "destination_lng": live_progress["destination_lng"],
        "initial_distance_meters": live_progress["initial_distance_meters"],
        "last_location": live_progress["last_location"] or fallback_last_location,
    }


async def _build_public_tracking_snapshot_async(db: Session, order: Order) -> dict:
    payload = _build_public_tracking_snapshot(db, order)
    live_progress = await _load_live_progress_snapshot_async(db, order)
    payload["progress"] = live_progress["progress"]
    payload["distance_meters"] = live_progress["distance_meters"]
    payload["duration_seconds"] = live_progress["duration_seconds"]
    payload["driver_lat"] = live_progress["driver_lat"]
    payload["driver_lng"] = live_progress["driver_lng"]
    payload["destination_lat"] = live_progress["destination_lat"]
    payload["destination_lng"] = live_progress["destination_lng"]
    payload["initial_distance_meters"] = live_progress["initial_distance_meters"]
    payload["last_location"] = live_progress["last_location"] or payload.get("last_location")
    return payload


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

    for field_name in (
        "progress",
        "distance_meters",
        "duration_seconds",
        "driver_lat",
        "driver_lng",
        "destination_lat",
        "destination_lng",
        "initial_distance_meters",
    ):
        if payload.get(field_name) is not None:
            normalized_payload[field_name] = payload.get(field_name)

    if lat is not None and lng is not None:
        try:
            normalized_payload["last_location"] = {"lat": float(lat), "lng": float(lng)}
            normalized_payload["driver_lat"] = float(lat)
            normalized_payload["driver_lng"] = float(lng)
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


def _build_public_order_payload(db: Session, order: Order) -> dict:
    items = (
        db.query(OrderItem)
        .filter(OrderItem.order_id == int(order.id))
        .order_by(OrderItem.id.asc())
        .all()
    )
    tenant = db.query(Tenant).filter(Tenant.id == int(order.tenant_id)).first()
    public_settings = (
        db.query(TenantPublicSettings)
        .filter(TenantPublicSettings.tenant_id == int(order.tenant_id))
        .first()
    )
    raw_status, normalized_status, status_step, status_label = _resolve_tracking_metadata(order)
    estimated_minutes = _resolve_estimated_minutes(order)
    live_progress = _load_live_progress_snapshot(db, order)
    order_total_cents = getattr(order, "total_cents", None)
    if order_total_cents in (None, ""):
        order_total_cents = getattr(order, "valor_total", None)

    store_name = (
        getattr(tenant, "business_name", None)
        or getattr(tenant, "name", None)
        or "Restaurante"
    )

    return {
        "order_number": int(order.daily_order_number or order.id),
        "order_id": int(order.id),
        "status": normalized_status,
        "status_raw": raw_status,
        "status_label": status_label,
        "status_step": status_step,
        "order_type": _resolve_order_type_label(order),
        "items": [{"name": str(item.name or ""), "quantity": int(item.quantity or 0)} for item in items],
        "total": float(order_total_cents or 0),
        "total_cents": int(order_total_cents or 0),
        "payment_method": order.payment_method,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "ready_at": order.ready_at.isoformat() if order.ready_at else None,
        "start_delivery_at": order.start_delivery_at.isoformat() if order.start_delivery_at else None,
        "estimated_minutes": estimated_minutes,
        "progress": live_progress["progress"],
        "distance_meters": live_progress["distance_meters"],
        "duration_seconds": live_progress["duration_seconds"],
        "driver_lat": live_progress["driver_lat"],
        "driver_lng": live_progress["driver_lng"],
        "destination_lat": live_progress["destination_lat"],
        "destination_lng": live_progress["destination_lng"],
        "initial_distance_meters": live_progress["initial_distance_meters"],
        "last_location": live_progress["last_location"],
        "store_name": store_name,
        "store_logo_url": getattr(public_settings, "logo_url", None),
        "primary_color": getattr(public_settings, "primary_color", None),
    }


@router.get("/public/track/{tracking_token}", include_in_schema=False)
@router.get("/api/public/track/{tracking_token}")
def get_public_tracking(tracking_token: str, request: Request, db: Session = Depends(get_db)):
    try:
        order = _resolve_public_tracking_order(db, tracking_token, request)
    except TrackingNotFound as exc:
        raise HTTPException(status_code=404, detail="Rastreamento não encontrado") from exc

    return JSONResponse(
        content=_build_public_tracking_snapshot(db, order),
        headers=NO_CACHE_HEADERS,
    )


@router.get("/public/order/{tracking_token}", include_in_schema=False)
@router.get("/api/public/order/{tracking_token}")
def get_public_order_tracking(tracking_token: str, request: Request, db: Session = Depends(get_db)):
    try:
        order = _resolve_public_tracking_order(db, tracking_token, request)
    except TrackingNotFound as exc:
        raise HTTPException(status_code=404, detail="Pedido não encontrado") from exc

    return JSONResponse(
        content=_build_public_order_payload(db, order),
        headers=NO_CACHE_HEADERS,
    )




@router.get("/public/tracking/{tracking_token}", include_in_schema=False)
@router.get("/api/public/tracking/{tracking_token}")
@router.get("/public/sse/{tracking_token}", include_in_schema=False)
@router.get("/api/public/sse/{tracking_token}")
async def sse_public_tracking(tracking_token: str, request: Request):
    db = SessionLocal()
    try:
        order = _resolve_public_tracking_order(db, tracking_token, request)
        tenant_id = int(order.tenant_id)
        order_id = int(order.id)
        initial_payload = await _build_public_tracking_snapshot_async(db, order)
    except TrackingNotFound as exc:
        raise HTTPException(status_code=404, detail="Rastreamento não encontrado") from exc
    finally:
        db.close()

    async def event_generator():
        initial_payload.setdefault("event", "tracking_update")
        if initial_payload.get("driver_lat") is not None and initial_payload.get("driver_lng") is not None:
            logger.info(
                "public_tracking_update",
                extra={
                    "driver_lat": initial_payload.get("driver_lat"),
                    "driver_lng": initial_payload.get("driver_lng"),
                    "distance_meters": initial_payload.get("distance_meters"),
                    "duration_seconds": initial_payload.get("duration_seconds"),
                },
            )
            yield f"event: tracking_update\ndata: {json.dumps(initial_payload)}\n\n"
            yield f"event: driver_update\ndata: {json.dumps(initial_payload)}\n\n"

        redis = get_async_redis_client()
        pubsub = redis.pubsub() if redis is not None else None
        last_progress_payload = {
            "progress": initial_payload.get("progress"),
            "distance_meters": initial_payload.get("distance_meters"),
            "duration_seconds": initial_payload.get("duration_seconds"),
            "driver_lat": initial_payload.get("driver_lat"),
            "driver_lng": initial_payload.get("driver_lng"),
            "destination_lat": initial_payload.get("destination_lat"),
            "destination_lng": initial_payload.get("destination_lng"),
            "initial_distance_meters": initial_payload.get("initial_distance_meters"),
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
                    if isinstance(live_location, dict) and live_location.get("lat") is not None and live_location.get("lng") is not None:
                        live_lat = float(live_location["lat"])
                        live_lng = float(live_location["lng"])
                        distance_meters, duration_seconds = await _resolve_route_metrics(
                            live_lat,
                            live_lng,
                            last_progress_payload.get("destination_lat"),
                            last_progress_payload.get("destination_lng"),
                        )
                        current_progress_payload = {
                            "event": "tracking_update",
                            "status": "OUT_FOR_DELIVERY",
                            "progress": last_progress_payload.get("progress"),
                            "distance_meters": distance_meters,
                            "duration_seconds": duration_seconds,
                            "driver_lat": live_lat,
                            "driver_lng": live_lng,
                            "destination_lat": last_progress_payload.get("destination_lat"),
                            "destination_lng": last_progress_payload.get("destination_lng"),
                            "initial_distance_meters": last_progress_payload.get("initial_distance_meters"),
                            "last_location": {
                                "lat": live_lat,
                                "lng": live_lng,
                                "updated_at": live_location.get("updated_at"),
                            },
                        }
                        if current_progress_payload.get("initial_distance_meters") is None and distance_meters is not None:
                            current_progress_payload["initial_distance_meters"] = distance_meters
                        baseline_distance = current_progress_payload.get("initial_distance_meters")
                        if baseline_distance is not None and distance_meters is not None:
                            current_progress_payload["progress"] = _clamp_progress(1 - (distance_meters / max(int(baseline_distance), 1)))
                        if current_progress_payload != last_progress_payload:
                            logger.info(
                                "public_tracking_update",
                                extra={
                                    "driver_lat": current_progress_payload.get("driver_lat"),
                                    "driver_lng": current_progress_payload.get("driver_lng"),
                                    "distance_meters": current_progress_payload.get("distance_meters"),
                                    "duration_seconds": current_progress_payload.get("duration_seconds"),
                                },
                            )
                            last_progress_payload = current_progress_payload.copy()
                            yield f"event: tracking_update\ndata: {json.dumps(current_progress_payload)}\n\n"
                            yield f"event: driver_update\ndata: {json.dumps(current_progress_payload)}\n\n"

                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0) if pubsub is not None else None
                if message is not None:
                    raw_payload = message.get("data")
                    payload_text = raw_payload.decode() if isinstance(raw_payload, bytes) else str(raw_payload)
                    payload_data = parse_delivery_envelope(payload_text, expected_tenant_id=tenant_id)
                    if payload_data is not None:
                        normalized_payload = _build_public_tracking_event(payload_data)
                        if normalized_payload is not None:
                            normalized_payload.setdefault("event", "tracking_update")
                            for field_name in last_progress_payload:
                                if normalized_payload.get(field_name) is not None:
                                    last_progress_payload[field_name] = normalized_payload[field_name]
                            if normalized_payload.get("driver_lat") is not None and normalized_payload.get("driver_lng") is not None:
                                logger.info(
                                    "public_tracking_update",
                                    extra={
                                        "driver_lat": normalized_payload.get("driver_lat"),
                                        "driver_lng": normalized_payload.get("driver_lng"),
                                        "distance_meters": normalized_payload.get("distance_meters"),
                                        "duration_seconds": normalized_payload.get("duration_seconds"),
                                    },
                                )
                                yield f"event: tracking_update\ndata: {json.dumps(normalized_payload)}\n\n"
                                yield f"event: driver_update\ndata: {json.dumps(normalized_payload)}\n\n"
                            continue

                heartbeat_payload = {
                    "driver_lat": last_progress_payload.get("driver_lat"),
                    "driver_lng": last_progress_payload.get("driver_lng"),
                    "distance_meters": last_progress_payload.get("distance_meters"),
                    "duration_seconds": last_progress_payload.get("duration_seconds"),
                }
                if heartbeat_payload.get("driver_lat") is not None and heartbeat_payload.get("driver_lng") is not None:
                    heartbeat_payload["event"] = "tracking_update"
                    logger.info("public_tracking_update", extra=heartbeat_payload)
                    yield f"event: tracking_update\ndata: {json.dumps(heartbeat_payload)}\n\n"
                    yield f"event: driver_update\ndata: {json.dumps(heartbeat_payload)}\n\n"
                else:
                    yield ": keep-alive\n\n"
                await asyncio.sleep(2)
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
def get_order_by_tracking_token(tracking_token: str, request: Request, db: Session = Depends(get_db)):
    try:
        order = _resolve_public_tracking_order(db, tracking_token, request)
    except TrackingNotFound as exc:
        raise HTTPException(status_code=404, detail="Pedido não encontrado") from exc

    return JSONResponse(
        content={
            "tracking_token": str(order.tracking_token or ""),
            "status": str(order.status or ""),
        },
        headers=NO_CACHE_HEADERS,
    )
