from __future__ import annotations

import asyncio
import logging
import traceback
from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import AliasChoices, BaseModel, EmailStr, Field
from sqlalchemy import desc, func, update
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import get_current_delivery_user
from app.models.admin_user import AdminUser
from app.models.delivery_tracking import DeliveryTracking
from app.models.order import Order
from app.services.geocoding_service import geocode_address
from app.services.auth import create_access_token
from app.realtime.publisher import publish_delivery_driver_location_event, publish_public_tracking_event
from app.integrations.redis_client import get_async_redis_client
from app.services.order_events import emit_order_status_changed
from app.services.directions_service import get_route_metrics_with_fallback
from app.modules.tracking.service import save_delivery_location, save_delivery_total_distance
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
    order_id: int = Field(validation_alias=AliasChoices("order_id", "delivery_id"))
    lat: float = Field(validation_alias=AliasChoices("lat", "latitude"))
    lng: float = Field(validation_alias=AliasChoices("lng", "longitude"))


class DriverLocationRejected(Exception):
    def __init__(self, reason: str, status_code: int = 422):
        super().__init__(reason)
        self.reason = reason
        self.status_code = status_code


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
    customer_lat = float(order.customer_lat) if order.customer_lat is not None else (float(order.delivery_lat) if order.delivery_lat is not None else None)
    customer_lng = float(order.customer_lng) if order.customer_lng is not None else (float(order.delivery_lng) if order.delivery_lng is not None else None)

    return {
        "id": int(order.id),
        "daily_order_number": order.daily_order_number,
        "status": _normalize_workflow_status(order.status),
        "raw_status": order.status,
        "customer_name": order.customer_name or order.cliente_nome,
        "phone": order.customer_phone or order.cliente_telefone,
        "address": _build_order_address(order),
        "neighborhood": order.neighborhood or (order.delivery_address_json or {}).get("neighborhood") if isinstance(order.delivery_address_json, dict) else order.neighborhood,
        "complement": order.complement,
        "reference": order.reference,
        "notes": order.order_note or order.observacao,
        "payment_method": order.payment_method or order.forma_pagamento,
        "change_for": float(order.payment_change_for or order.change_for) if (order.payment_change_for is not None or order.change_for is not None) else None,
        "order_type": order.order_type or order.tipo_entrega,
        "total_cents": int(order.total_cents or order.valor_total or 0),
        "items": order.items_json or order.itens,
        "delivery_lat": float(order.delivery_lat) if order.delivery_lat is not None else None,
        "delivery_lng": float(order.delivery_lng) if order.delivery_lng is not None else None,
        "customer_lat": customer_lat,
        "customer_lng": customer_lng,
        "destination_lat": float(order.destination_lat) if order.destination_lat is not None else customer_lat,
        "destination_lng": float(order.destination_lng) if order.destination_lng is not None else customer_lng,
        "latitude": customer_lat,
        "longitude": customer_lng,
        "created_at": order.created_at.isoformat() if order.created_at else None,
    }


def _coordinates_are_valid(lat: float | None, lng: float | None) -> bool:
    if lat is None or lng is None:
        return False
    return -90 <= lat <= 90 and -180 <= lng <= 180


def _run_geocode(address: str) -> tuple[float | None, float | None]:
    try:
        return asyncio.run(geocode_address(address))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(geocode_address(address))
        finally:
            loop.close()


def _ensure_order_destination_coordinates(order: Order) -> None:
    current_lat = float(order.destination_lat) if order.destination_lat is not None else (float(order.customer_lat) if order.customer_lat is not None else None)
    current_lng = float(order.destination_lng) if order.destination_lng is not None else (float(order.customer_lng) if order.customer_lng is not None else None)
    fallback_lat = float(order.delivery_lat) if order.delivery_lat is not None else None
    fallback_lng = float(order.delivery_lng) if order.delivery_lng is not None else None

    if _coordinates_are_valid(current_lat, current_lng):
        order.destination_lat = current_lat
        order.destination_lng = current_lng
        logger.info("[DriverRouting] using order coordinates order_id=%s lat=%s lng=%s", order.id, current_lat, current_lng)
        return

    if _coordinates_are_valid(fallback_lat, fallback_lng):
        order.customer_lat = fallback_lat
        order.customer_lng = fallback_lng
        order.destination_lat = fallback_lat
        order.destination_lng = fallback_lng
        logger.warning(
            "[DriverRouting] customer coordinates missing/invalid, using delivery fallback order_id=%s lat=%s lng=%s",
            order.id,
            fallback_lat,
            fallback_lng,
        )
        return

    geocoding_query = _build_order_address(order)
    geocoded_lat, geocoded_lng = _run_geocode(geocoding_query)
    if _coordinates_are_valid(geocoded_lat, geocoded_lng):
        order.customer_lat = geocoded_lat
        order.customer_lng = geocoded_lng
        order.destination_lat = geocoded_lat
        order.destination_lng = geocoded_lng
        if order.delivery_lat is None or order.delivery_lng is None:
            order.delivery_lat = geocoded_lat
            order.delivery_lng = geocoded_lng
        logger.warning(
            "[DriverRouting] geocoded order destination order_id=%s query=%r lat=%s lng=%s",
            order.id,
            geocoding_query,
            geocoded_lat,
            geocoded_lng,
        )
        return

    logger.error(
        "[DriverRouting] unable to resolve destination coordinates order_id=%s query=%r",
        order.id,
        geocoding_query,
    )


def _resolve_destination_coordinates(order: Order) -> tuple[float | None, float | None]:
    destination_lat = float(order.destination_lat) if order.destination_lat is not None else None
    destination_lng = float(order.destination_lng) if order.destination_lng is not None else None
    if _coordinates_are_valid(destination_lat, destination_lng):
        return destination_lat, destination_lng

    customer_lat = float(order.customer_lat) if order.customer_lat is not None else None
    customer_lng = float(order.customer_lng) if order.customer_lng is not None else None
    if _coordinates_are_valid(customer_lat, customer_lng):
        return customer_lat, customer_lng

    delivery_lat = float(order.delivery_lat) if order.delivery_lat is not None else None
    delivery_lng = float(order.delivery_lng) if order.delivery_lng is not None else None
    if _coordinates_are_valid(delivery_lat, delivery_lng):
        return delivery_lat, delivery_lng

    return None, None


async def _recalculate_tracking_metrics(order: Order, tracking: DeliveryTracking) -> tuple[int | None, int | None, float]:
    destination_lat, destination_lng = _resolve_destination_coordinates(order)
    if not _coordinates_are_valid(destination_lat, destination_lng):
        return None, None, 0.0

    distance_meters, duration_seconds, _geometry, _provider = await get_route_metrics_with_fallback(
        tracking.current_lat,
        tracking.current_lng,
        destination_lat,
        destination_lng,
    )
    tracking.route_distance_meters = max(0, int(distance_meters)) if distance_meters is not None else None
    tracking.route_duration_seconds = max(0, int(duration_seconds)) if duration_seconds is not None else None
    if tracking.initial_distance_meters is None and tracking.route_distance_meters is not None:
        tracking.initial_distance_meters = tracking.route_distance_meters

    if tracking.route_duration_seconds is not None:
        tracking.expected_delivery_at = datetime.now(timezone.utc)

    if tracking.initial_distance_meters is None or tracking.route_distance_meters is None:
        progress = 0.0
    else:
        progress = max(0.0, min(1.0, 1 - (tracking.route_distance_meters / max(tracking.initial_distance_meters, 1))))

    return tracking.route_distance_meters, tracking.route_duration_seconds, progress


async def _store_total_delivery_distance(order: Order, driver_lat: float | None, driver_lng: float | None) -> float | None:
    if driver_lat is None or driver_lng is None:
        return None
    destination_lat, destination_lng = _resolve_destination_coordinates(order)
    if not _coordinates_are_valid(destination_lat, destination_lng):
        return None

    route_distance_meters, _route_duration_seconds, _geometry, _provider = await get_route_metrics_with_fallback(
        driver_lat,
        driver_lng,
        destination_lat,
        destination_lng,
    )
    total_distance_km = max(0.001, float(route_distance_meters) / 1000)

    redis = get_async_redis_client()
    try:
        await save_delivery_total_distance(redis, int(order.id), total_distance_km)
    finally:
        if redis is not None:
            await redis.aclose()
    return total_distance_km


async def process_driver_location_update(
    *,
    authenticated_driver: AdminUser,
    db: Session,
    delivery_id: int,
    latitude: float,
    longitude: float,
    accuracy: float | None = None,
    speed: float | None = None,
    heading: float | None = None,
    recorded_at: str | None = None,
    enforce_rate_limit: bool = True,
) -> dict[str, Any]:
    tenant_id = int(authenticated_driver.tenant_id)
    driver_id = int(authenticated_driver.id)
    role = str(getattr(authenticated_driver, "role", "")).upper()
    if role not in {"DELIVERY", "DRIVER"}:
        raise DriverLocationRejected("unauthorized_role", status_code=403)
    if not _coordinates_are_valid(latitude, longitude):
        raise DriverLocationRejected("invalid_coordinates")
    if accuracy is not None and (accuracy < 0 or accuracy > 10000):
        raise DriverLocationRejected("invalid_accuracy")

    parsed_recorded_at = None
    if recorded_at:
        try:
            parsed_recorded_at = datetime.fromisoformat(str(recorded_at).replace("Z", "+00:00"))
        except ValueError as exc:
            raise DriverLocationRejected("invalid_timestamp") from exc
        now = datetime.now(timezone.utc)
        if parsed_recorded_at.tzinfo is None:
            parsed_recorded_at = parsed_recorded_at.replace(tzinfo=timezone.utc)
        if parsed_recorded_at < now - timedelta(hours=1) or parsed_recorded_at > now + timedelta(minutes=5):
            raise DriverLocationRejected("invalid_timestamp")

    order = db.query(Order).filter(Order.id == int(delivery_id), Order.tenant_id == tenant_id).first()
    if order is None:
        raise DriverLocationRejected("delivery_not_found", status_code=404)
    if int(order.assigned_delivery_user_id or 0) != driver_id:
        raise DriverLocationRejected("delivery_not_assigned", status_code=409)
    if (order.status or "").upper() not in (DRIVER_ASSIGNED_STATUSES | OUT_FOR_DELIVERY_STATUSES):
        raise DriverLocationRejected("delivery_not_trackable", status_code=409)

    redis = get_async_redis_client()
    try:
        if enforce_rate_limit and redis is not None:
            from app.modules.tracking.service import can_accept_location_update
            if not await can_accept_location_update(redis, int(order.id), driver_id):
                raise DriverLocationRejected("rate_limited", status_code=429)

        _ensure_order_destination_coordinates(order)
        tracking = db.query(DeliveryTracking).filter(DeliveryTracking.order_id == int(order.id)).first()
        if tracking is None:
            tracking = DeliveryTracking(
                order_id=int(order.id),
                delivery_user_id=driver_id,
                estimated_duration_seconds=0,
                expected_delivery_at=datetime.now(timezone.utc),
            )
            db.add(tracking)

        order.driver_lat = float(latitude)
        order.driver_lng = float(longitude)
        tracking.current_lat = float(latitude)
        tracking.current_lng = float(longitude)
        tracking.delivery_user_id = driver_id

        distance_meters = None
        duration_seconds = None
        total_distance_km = None
        progress = 0.0
        if (order.status or "").upper() in OUT_FOR_DELIVERY_STATUSES:
            distance_meters, duration_seconds, progress = await _recalculate_tracking_metrics(order, tracking)
        db.commit()

        location_payload = await save_delivery_location(
            redis,
            order_id=int(order.id),
            lat=float(latitude),
            lng=float(longitude),
            accuracy=accuracy,
            speed=speed,
            heading=heading,
            recorded_at=str(recorded_at) if recorded_at else None,
        )
        if (order.status or "").upper() in OUT_FOR_DELIVERY_STATUSES:
            total_distance_km = await _store_total_delivery_distance(order, float(latitude), float(longitude))
    finally:
        if redis is not None:
            await redis.aclose()

    publish_delivery_driver_location_event(tenant_id=tenant_id, driver_id=driver_id, order_id=int(order.id), lat=latitude, lng=longitude)
    if (order.status or "").upper() in OUT_FOR_DELIVERY_STATUSES:
        publish_public_tracking_event(
            tenant_id=tenant_id,
            order_id=int(order.id),
            status=order.status,
            delivery_user_name=getattr(authenticated_driver, "name", None),
            lat=latitude,
            lng=longitude,
            distance_meters=distance_meters,
            duration_seconds=duration_seconds,
            initial_distance_meters=getattr(tracking, "initial_distance_meters", None),
            progress=progress,
            updated_at=location_payload.get("updated_at") if isinstance(location_payload, dict) else None,
        )

    return {
        "ok": True,
        "success": True,
        "delivery_id": int(order.id),
        "location": location_payload,
        "total_distance_km": total_distance_km,
        "distance_meters": distance_meters,
        "duration_seconds": duration_seconds,
        "initial_distance_meters": getattr(tracking, "initial_distance_meters", None),
        "progress": progress,
    }


def _build_order_address(order: Order) -> str:
    delivery_address = getattr(order, "delivery_address_json", None)
    delivery_address = delivery_address if isinstance(delivery_address, dict) else {}

    def _clean(value: Any) -> str:
        return str(value or "").strip()

    def _pick(*values: Any) -> str:
        for value in values:
            cleaned = _clean(value)
            if cleaned:
                return cleaned
        return ""

    street = _pick(getattr(order, "street", None), delivery_address.get("street"))
    number = _pick(getattr(order, "number", None), delivery_address.get("number"))
    complement = _pick(getattr(order, "complement", None), delivery_address.get("complement"))
    neighborhood = _pick(
        getattr(order, "neighborhood", None),
        delivery_address.get("neighborhood"),
        delivery_address.get("district"),
    )
    city = _pick(getattr(order, "city", None), delivery_address.get("city"))
    state = _pick(delivery_address.get("state"))
    zip_code = _pick(delivery_address.get("zip"), delivery_address.get("cep"))
    country = _pick(delivery_address.get("country"), "Brasil")

    address_parts = [part for part in [street, number, complement, neighborhood, city, state, zip_code] if part]
    if address_parts:
        return ", ".join([*address_parts, country])

    fallback_address = _clean(getattr(order, "endereco", ""))
    return fallback_address or country


@router.post("/auth/login")
def driver_login(payload: DriverLoginPayload, request: Request, db: Session = Depends(get_db)):
    tenant = getattr(request.state, "tenant", None)
    if tenant is None:
        raise HTTPException(status_code=400, detail="Tenant não resolvido")

    driver = (
        db.query(AdminUser)
        .filter(
            AdminUser.tenant_id == int(tenant.id),
            func.upper(AdminUser.role).in_(["DELIVERY", "DRIVER"]),
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

    if active_delivery is not None:
        _ensure_order_destination_coordinates(active_delivery)
        db.add(active_delivery)
        db.commit()

    assigned_orders = (
        db.query(Order)
        .filter(
            Order.tenant_id == tenant_id,
            Order.assigned_delivery_user_id == driver_id,
            ~func.upper(Order.status).in_(DELIVERED_STATUSES | {"CANCELLED"}),
        )
        .order_by(desc(Order.created_at), desc(Order.id))
        .all()
    )

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    completed_today = (
        db.query(func.count(Order.id))
        .filter(
            Order.tenant_id == tenant_id,
            Order.assigned_delivery_user_id == driver_id,
            func.upper(Order.status).in_(DELIVERED_STATUSES),
            Order.created_at >= today_start,
        )
        .scalar()
        or 0
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
        "assigned_orders": [_serialize_order(order) for order in assigned_orders],
        "completed_today": int(completed_today),
    }


@router.get("/deliveries")
def list_driver_deliveries(db: Session = Depends(get_db), current_driver: AdminUser = Depends(get_current_delivery_user)):
    return get_driver_state(db=db, current_driver=current_driver)


@router.get("/deliveries/{delivery_id}")
def get_driver_delivery(delivery_id: int, db: Session = Depends(get_db), current_driver: AdminUser = Depends(get_current_delivery_user)):
    order = db.query(Order).filter(Order.id == int(delivery_id), Order.tenant_id == int(current_driver.tenant_id)).first()
    if order is None:
        raise HTTPException(status_code=404, detail="Entrega não encontrada")
    if order.assigned_delivery_user_id is not None and int(order.assigned_delivery_user_id) != int(current_driver.id):
        raise HTTPException(status_code=404, detail="Entrega não encontrada")
    if order.assigned_delivery_user_id is None and (order.status or "").upper() not in READY_FOR_DELIVERY_STATUSES:
        raise HTTPException(status_code=404, detail="Entrega não encontrada")
    return _serialize_order(order)


@router.post("/deliveries/{delivery_id}/accept")
def accept_delivery(delivery_id: int, db: Session = Depends(get_db), current_driver: AdminUser = Depends(get_current_delivery_user)):
    return accept_order(delivery_id, db=db, current_driver=current_driver)


@router.post("/orders/{order_id}/accept")
def accept_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_driver: AdminUser = Depends(get_current_delivery_user),
):
    tenant_id = int(current_driver.tenant_id)
    driver_id = int(current_driver.id)
    result = db.execute(
        update(Order)
        .where(
            Order.id == int(order_id),
            Order.tenant_id == tenant_id,
            Order.assigned_delivery_user_id.is_(None),
            func.upper(Order.status).in_(READY_FOR_DELIVERY_STATUSES),
        )
        .values(assigned_delivery_user_id=driver_id, status="DRIVER_ASSIGNED")
    )
    if int(getattr(result, "rowcount", 0) or 0) != 1:
        db.rollback()
        existing = db.query(Order).filter(Order.id == int(order_id), Order.tenant_id == tenant_id).first()
        if existing is None:
            raise HTTPException(status_code=404, detail="Pedido não encontrado")
        if int(existing.assigned_delivery_user_id or 0) == driver_id:
            return {"ok": True, "status": existing.status, "order_id": existing.id}
        raise HTTPException(status_code=409, detail="Pedido indisponível para aceite")
    order = db.query(Order).filter(Order.id == int(order_id), Order.tenant_id == tenant_id, Order.assigned_delivery_user_id == driver_id).first()
    db.commit()
    if order is not None:
        emit_order_status_changed(order, "READY_FOR_DELIVERY")
    return {"ok": True, "status": "DRIVER_ASSIGNED", "order_id": order_id}


@router.post("/orders/{order_id}/start")
async def start_order(
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

    _ensure_order_destination_coordinates(order)

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

    tracking = db.query(DeliveryTracking).filter(DeliveryTracking.order_id == int(order.id)).first()
    if tracking is None:
        tracking = DeliveryTracking(
            order_id=int(order.id),
            delivery_user_id=int(current_driver.id),
            estimated_duration_seconds=0,
            expected_delivery_at=datetime.now(timezone.utc),
        )
        db.add(tracking)
        db.commit()
        db.refresh(tracking)
    driver_lat = float(tracking.current_lat) if tracking and tracking.current_lat is not None else None
    driver_lng = float(tracking.current_lng) if tracking and tracking.current_lng is not None else None
    if driver_lat is not None and driver_lng is not None:
        try:
            if tracking is not None:
                distance_meters, duration_seconds, _progress = await _recalculate_tracking_metrics(order, tracking)
                if tracking.initial_distance_meters is None and distance_meters is not None:
                    tracking.initial_distance_meters = distance_meters
                if duration_seconds is not None:
                    tracking.estimated_duration_seconds = duration_seconds
                db.add(tracking)
                db.commit()
            await _store_total_delivery_distance(order, driver_lat, driver_lng)
        except Exception:
            logger.exception("failed to initialize delivery distance order_id=%s", order.id)

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


@router.post("/deliveries/{path_delivery_id}/location")
@router.post("/location")
@router.post("/driver/location")
async def update_driver_location(
    request: Request,
    path_delivery_id: int | None = None,
    payload: DriverLocationPayload | None = Body(default=None),
    db: Session = Depends(get_db),
    current_driver: AdminUser = Depends(get_current_delivery_user),
):
    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        raw_json = await request.json()
        data = payload.model_dump() if payload is not None else raw_json
        if isinstance(raw_json, dict):
            for extra_key in ("delivery_id", "latitude", "longitude", "accuracy", "speed", "heading", "recorded_at"):
                if extra_key in raw_json:
                    data[extra_key] = raw_json[extra_key]
    else:
        form = await request.form()
        data = {
            "order_id": form.get("order_id"),
            "lat": form.get("lat"),
            "lng": form.get("lng"),
        }

    order_id = path_delivery_id or data.get("delivery_id") or data.get("order_id")
    lat = data.get("latitude") if data.get("latitude") is not None else data.get("lat")
    lng = data.get("longitude") if data.get("longitude") is not None else data.get("lng")
    accuracy = data.get("accuracy")
    speed = data.get("speed")
    heading = data.get("heading")
    recorded_at = data.get("recorded_at")

    if not order_id or lat is None or lng is None:
        raise HTTPException(status_code=400, detail="Missing location data")

    try:
        order_id = int(order_id)
        lat = float(lat)
        lng = float(lng)
        accuracy = float(accuracy) if accuracy is not None else None
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Missing location data") from exc

    tenant_id = int(current_driver.tenant_id)
    driver_id = int(current_driver.id)

    logger.info(
        "driver location update request driver_id=%s tenant_id=%s order_id=%s lat=%s lng=%s",
        driver_id,
        tenant_id,
        order_id,
        lat,
        lng,
    )

    try:
        if lat is None or lng is None or not _coordinates_are_valid(lat, lng):
            raise HTTPException(status_code=422, detail="Coordenadas inválidas")
        return await process_driver_location_update(
            authenticated_driver=current_driver,
            db=db,
            delivery_id=order_id,
            latitude=lat,
            longitude=lng,
            accuracy=accuracy,
            speed=float(speed) if speed is not None else None,
            heading=float(heading) if heading is not None else None,
            recorded_at=str(recorded_at) if recorded_at else None,
            enforce_rate_limit=False,
        )
    except DriverLocationRejected as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.reason) from exc
    except HTTPException:
        raise
    except Exception as err:
        db.rollback()
        logger.exception(
            "driver location update failed driver_id=%s tenant_id=%s order_id=%s",
            driver_id,
            tenant_id,
            order_id,
        )
        logger.error(
            "Driver location update error",
            extra={
                "driver_id": driver_id,
                "order_id": order_id,
                "error": str(err),
                "stack": traceback.format_exc(),
            },
        )
        return JSONResponse(
            status_code=200,
            content={
                "success": False,
                "error": "LOCATION_UPDATE_FAILED",
            },
        )


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
