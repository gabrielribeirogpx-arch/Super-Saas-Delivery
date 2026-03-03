from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.delivery_log import DeliveryLog
from app.models.order import Order
from app.realtime.publisher import publish_order_tracking_event
from app.services.route_optimizer import optimize_route


def generate_tracking_token() -> str:
    return str(uuid.uuid4())


def ensure_tracking_token(order: Order) -> None:
    if not getattr(order, "tracking_token", None):
        order.tracking_token = generate_tracking_token()


def is_tracking_expired(order: Order) -> bool:
    expires_at = getattr(order, "tracking_expires_at", None)
    if expires_at is None:
        return False
    return expires_at <= datetime.now(timezone.utc)


def expire_tracking_token(order: Order, *, grace_minutes: int = 0) -> None:
    base_time = datetime.now(timezone.utc)
    if grace_minutes > 0:
        base_time += timedelta(minutes=grace_minutes)
    order.tracking_expires_at = base_time


def _extract_destination_coords(order: Order) -> tuple[float, float] | None:
    raw_payload = getattr(order, "delivery_address_json", None)
    if not raw_payload:
        return None

    if isinstance(raw_payload, str):
        try:
            raw_payload = json.loads(raw_payload)
        except Exception:
            return None

    if not isinstance(raw_payload, dict):
        return None

    lat = raw_payload.get("latitude") or raw_payload.get("lat")
    lng = raw_payload.get("longitude") or raw_payload.get("lng") or raw_payload.get("lon")
    if lat is None or lng is None:
        return None

    try:
        return float(lat), float(lng)
    except (TypeError, ValueError):
        return None


def get_last_delivery_position(db: Session, tenant_id: int, delivery_user_id: int) -> tuple[float, float] | None:
    try:
        latest = (
            db.query(DeliveryLog)
            .filter(
                DeliveryLog.tenant_id == int(tenant_id),
                DeliveryLog.delivery_user_id == int(delivery_user_id),
                DeliveryLog.event_type == "location_update",
                DeliveryLog.latitude.isnot(None),
                DeliveryLog.longitude.isnot(None),
            )
            .order_by(DeliveryLog.created_at.desc())
            .first()
        )
    except AttributeError:
        return None
    if latest is None:
        return None
    return float(latest.latitude), float(latest.longitude)


def recalculate_order_tracking(
    order: Order,
    *,
    origin_lat: float,
    origin_lng: float,
) -> None:
    destination = _extract_destination_coords(order)
    if destination is None:
        return

    destination_lat, destination_lng = destination
    route = optimize_route([[origin_lng, origin_lat], [destination_lng, destination_lat]])
    routes = route.get("routes") or []
    if not routes:
        return

    summary = routes[0].get("summary") or {}
    geometry = routes[0].get("geometry") or ""

    distance = int(float(summary.get("distance", 0) or 0))
    duration = int(float(summary.get("duration", 0) or 0))

    order.polyline_encoded = str(geometry) if geometry else None
    order.route_distance_meters = distance if distance > 0 else None
    order.route_duration_seconds = duration if duration > 0 else None
    order.eta_seconds = duration if duration > 0 else None
    order.eta_at = datetime.now(timezone.utc) + timedelta(seconds=duration) if duration > 0 else None


def build_tracking_payload(order: Order, *, event: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "event": str(event),
        "status": str(getattr(order, "status", "") or ""),
        "tracking_token": getattr(order, "tracking_token", None),
        "polyline_encoded": getattr(order, "polyline_encoded", None),
        "distance_meters": getattr(order, "route_distance_meters", None),
        "duration_seconds": getattr(order, "route_duration_seconds", None),
        "eta_seconds": getattr(order, "eta_seconds", None),
        "eta_at": getattr(order, "eta_at", None).isoformat() if getattr(order, "eta_at", None) else None,
        "delivery_location": {
            "lat": getattr(order, "delivery_last_lat", None),
            "lng": getattr(order, "delivery_last_lng", None),
            "updated_at": getattr(order, "delivery_last_location_at", None).isoformat()
            if getattr(order, "delivery_last_location_at", None)
            else None,
        },
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if extra:
        payload.update(extra)
    return payload


def publish_tracking_snapshot(order: Order, *, event: str, extra: dict[str, Any] | None = None) -> int:
    payload = build_tracking_payload(order, event=event, extra=extra)
    return publish_order_tracking_event(int(order.tenant_id), int(order.id), payload)
