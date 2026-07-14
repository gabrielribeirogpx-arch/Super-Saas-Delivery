from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect

from app.integrations.redis_client import get_async_redis_client
from app.realtime.delivery_connections import delivery_connections
from app.realtime.delivery_envelope import parse_delivery_envelope
from app.realtime.publisher import (
    delivery_assignment_channel,
    delivery_driver_location_channel,
    delivery_location_channel,
    delivery_status_channel,
    publish_delivery_location_event,
    publish_delivery_status_event,
)
from app.services.admin_auth import ADMIN_SESSION_COOKIE, decode_admin_session
from app.services.auth import decode_access_token
from app.services.tenant_resolver import TenantResolver
from app.core.database import SessionLocal
from app.models.admin_user import AdminUser
from app.routers.driver_api import DriverLocationRejected, process_driver_location_update

logger = logging.getLogger(__name__)
router = APIRouter(tags=["delivery-realtime"])


def _extract_ws_token(websocket: WebSocket) -> str | None:
    auth_header = websocket.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        if token:
            return token

    token = websocket.cookies.get("access_token")
    if token:
        return token

    token = websocket.query_params.get("token")
    if token:
        return token

    return None


def _extract_connection_claims(token: str) -> tuple[int, int]:
    payload = decode_access_token(token)

    role = str(payload.get("role", "")).upper()
    if role != "DELIVERY":
        raise ValueError("Acesso permitido apenas para DELIVERY")

    tenant_id_raw = payload.get("tenant_id")
    delivery_user_id_raw = payload.get("delivery_user_id") or payload.get("user_id") or payload.get("sub")

    if tenant_id_raw is None or delivery_user_id_raw is None:
        raise ValueError("Token sem tenant_id ou delivery_user_id")

    return int(tenant_id_raw), int(delivery_user_id_raw)


def _driver_rejection(delivery_id: object, reason: str) -> dict:
    payload = {"type": "driver_location_rejected", "reason": reason}
    if delivery_id is not None:
        payload["delivery_id"] = delivery_id
    return payload


@router.websocket("/ws/driver")
async def driver_location_updates_ws(websocket: WebSocket):
    token = _extract_ws_token(websocket)
    if not token:
        await websocket.close(code=1008, reason="Token ausente")
        return

    try:
        tenant_id, delivery_user_id = _extract_connection_claims(token)
        resolved_tenant_id = TenantResolver.resolve_tenant_id_from_request(websocket)
        if resolved_tenant_id is not None and int(resolved_tenant_id) != int(tenant_id):
            raise ValueError("tenant_id incompatível com o token")
    except Exception:
        await websocket.close(code=1008, reason="Credenciais inválidas")
        return

    await websocket.accept()

    try:
        while True:
            try:
                payload = await websocket.receive_json()
            except WebSocketDisconnect:
                raise
            except Exception:
                await websocket.send_json(_driver_rejection(None, "malformed_payload"))
                continue

            delivery_id = payload.get("delivery_id") if isinstance(payload, dict) else None
            if not isinstance(payload, dict) or payload.get("type") != "driver_location_update":
                await websocket.send_json(_driver_rejection(delivery_id, "unknown_payload"))
                continue

            allowed = {"type", "delivery_id", "latitude", "longitude", "accuracy", "speed", "heading", "recorded_at"}
            if any(key not in allowed for key in payload.keys()):
                await websocket.send_json(_driver_rejection(delivery_id, "unknown_payload"))
                continue

            db = SessionLocal()
            try:
                driver = db.query(AdminUser).filter(
                    AdminUser.id == delivery_user_id,
                    AdminUser.tenant_id == tenant_id,
                ).first()
                if driver is None:
                    await websocket.send_json(_driver_rejection(delivery_id, "driver_not_found"))
                    continue

                result = await process_driver_location_update(
                    authenticated_driver=driver,
                    db=db,
                    delivery_id=int(payload["delivery_id"]),
                    latitude=float(payload["latitude"]),
                    longitude=float(payload["longitude"]),
                    accuracy=float(payload["accuracy"]) if payload.get("accuracy") is not None else None,
                    speed=float(payload["speed"]) if payload.get("speed") is not None else None,
                    heading=float(payload["heading"]) if payload.get("heading") is not None else None,
                    recorded_at=str(payload.get("recorded_at")) if payload.get("recorded_at") else None,
                    enforce_rate_limit=True,
                )
                await websocket.send_json({
                    "type": "driver_location_ack",
                    "delivery_id": result["delivery_id"],
                    "accepted": True,
                    "server_time": datetime.now(timezone.utc).isoformat(),
                })
            except (KeyError, TypeError, ValueError):
                await websocket.send_json(_driver_rejection(delivery_id, "invalid_payload"))
            except DriverLocationRejected as exc:
                await websocket.send_json(_driver_rejection(delivery_id, exc.reason))
            except Exception:
                logger.exception("driver websocket location update failed")
                await websocket.send_json(_driver_rejection(delivery_id, "internal_error"))
            finally:
                db.close()
    except WebSocketDisconnect:
        logger.info("event=driver_location_ws_disconnected tenant_id=%s delivery_user_id=%s", tenant_id, delivery_user_id)


@router.websocket("/ws/delivery")
async def delivery_ws(websocket: WebSocket):
    token = _extract_ws_token(websocket)
    if not token:
        await websocket.close(code=1008, reason="Token ausente")
        return

    try:
        tenant_id, delivery_user_id = _extract_connection_claims(token)
        resolved_tenant_id = TenantResolver.resolve_tenant_id_from_request(websocket)
        if resolved_tenant_id is not None and int(resolved_tenant_id) != int(tenant_id):
            raise ValueError("tenant_id incompatível com o token")
    except Exception as exc:
        await websocket.close(code=1008, reason=str(exc))
        return

    await websocket.accept()
    await delivery_connections.set(tenant_id, delivery_user_id, websocket)
    publish_delivery_status_event(tenant_id=tenant_id, delivery_user_id=delivery_user_id, status="online")

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.debug(
            "Delivery websocket disconnected tenant_id=%s delivery_user_id=%s",
            tenant_id,
            delivery_user_id,
        )
    finally:
        await delivery_connections.remove(tenant_id, delivery_user_id, websocket)
        publish_delivery_status_event(tenant_id=tenant_id, delivery_user_id=delivery_user_id, status="offline")


@router.websocket("/ws/delivery/location")
async def delivery_location_ws(websocket: WebSocket):
    client_host = websocket.client.host if websocket.client else "unknown"

    tenant_id: int | None = None
    delivery_user_id: int | None = None

    try:
        token = _extract_ws_token(websocket)
        if not token:
            raise ValueError("Token ausente")

        payload = decode_access_token(token)
        role = str(payload.get("role", "")).strip().lower()
        if role != "delivery":
            raise ValueError("Acesso permitido apenas para delivery")

        tenant_id_raw = payload.get("tenant_id")
        delivery_user_id_raw = payload.get("delivery_user_id")
        if tenant_id_raw is None or delivery_user_id_raw is None:
            raise ValueError("Token sem tenant_id ou delivery_user_id")

        tenant_id = int(tenant_id_raw)
        delivery_user_id = int(delivery_user_id_raw)

        resolved_tenant_id = TenantResolver.resolve_tenant_id_from_request(websocket)
        if resolved_tenant_id is not None and int(resolved_tenant_id) != int(tenant_id):
            raise ValueError("tenant_id incompatível com o token")

        await websocket.accept()

        logger.info(
            "event=delivery_location_ws_authenticated tenant_id=%s delivery_user_id=%s client=%s",
            tenant_id,
            delivery_user_id,
            client_host,
        )

        while True:
            payload_data = await websocket.receive_json()
            lat = float(payload_data["lat"])
            lng = float(payload_data["lng"])
            status = str(payload_data.get("status", "unknown"))

            publish_delivery_location_event(
                tenant_id=tenant_id,
                delivery_user_id=delivery_user_id,
                lat=lat,
                lng=lng,
                status=status,
            )
    except WebSocketDisconnect:
        logger.info(
            "event=delivery_location_ws_disconnected tenant_id=%s delivery_user_id=%s client=%s",
            tenant_id,
            delivery_user_id,
            client_host,
        )
    except Exception as exc:
        logger.warning(
            "event=delivery_location_ws_error tenant_id=%s delivery_user_id=%s client=%s error=%s",
            tenant_id,
            delivery_user_id,
            client_host,
            exc,
        )
        await websocket.close(code=1008, reason=str(exc))


@router.websocket("/ws/admin/delivery-status")
async def admin_delivery_status_ws(websocket: WebSocket):
    client_host = websocket.client.host if websocket.client else "unknown"

    tenant_id_param = websocket.query_params.get("tenant_id")
    logger.info(
        "event=admin_delivery_ws_connection_started tenant_id_param=%s client=%s",
        tenant_id_param,
        client_host,
    )
    logger.info(
        "event=admin_delivery_ws_tenant_received tenant_id_param=%s client=%s",
        tenant_id_param,
        client_host,
    )

    try:
        if tenant_id_param is None:
            raise ValueError("tenant_id ausente")

        tenant_id = int(tenant_id_param)

        token = websocket.cookies.get(ADMIN_SESSION_COOKIE)
        if not token:
            raise ValueError("Admin não autenticado")

        payload = decode_admin_session(token)
        if not payload:
            raise ValueError("Sessão expirada")

        role = str(payload.get("role", "")).strip().lower()
        if role != "admin":
            raise ValueError("Acesso permitido apenas para ADMIN")

        tenant_id_raw = payload.get("tenant_id")
        if tenant_id_raw is None:
            raise ValueError("Sessão sem tenant_id")

        session_tenant_id = int(tenant_id_raw)
        if session_tenant_id != tenant_id:
            raise ValueError("tenant_id inválido para a sessão")

        logger.info(
            "event=admin_delivery_ws_auth_validated tenant_id=%s session_tenant_id=%s role=%s client=%s",
            tenant_id,
            session_tenant_id,
            role,
            client_host,
        )
    except Exception as exc:
        logger.warning(
            "event=admin_delivery_ws_auth_failed tenant_id_param=%s client=%s error=%s",
            tenant_id_param,
            client_host,
            exc,
        )
        await websocket.close(code=1008, reason=str(exc))
        return

    try:
        await websocket.accept()
    except Exception as exc:
        logger.exception(
            "event=admin_delivery_ws_accept_failed client=%s error=%s",
            client_host,
            exc,
        )
        return

    logger.info("event=admin_delivery_ws_connection_accepted client=%s", client_host)

    client = get_async_redis_client()
    if client is None:
        logger.error(
            "event=admin_delivery_ws_redis_unavailable tenant_id=%s client=%s",
            tenant_id,
            client_host,
        )
        await websocket.close(code=1011, reason="Redis indisponível")
        return

    status_channel = delivery_status_channel(tenant_id)
    location_channel = delivery_location_channel(tenant_id)
    driver_location_channel = delivery_driver_location_channel(tenant_id)
    assignment_channel = delivery_assignment_channel(tenant_id)
    pubsub = client.pubsub()

    logger.info(
        "event=admin_delivery_ws_connection_authenticated tenant_id=%s status_channel=%s location_channel=%s driver_location_channel=%s assignment_channel=%s client=%s",
        tenant_id,
        status_channel,
        location_channel,
        driver_location_channel,
        assignment_channel,
        client_host,
    )

    try:
        await pubsub.subscribe(status_channel, location_channel, driver_location_channel, assignment_channel)
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
        logger.info(
            "event=admin_delivery_ws_disconnected tenant_id=%s client=%s",
            tenant_id,
            client_host,
        )
    except Exception as exc:
        logger.exception(
            "event=admin_delivery_ws_runtime_error tenant_id=%s client=%s error=%s",
            tenant_id,
            client_host,
            exc,
        )
        await websocket.close(code=1011, reason="Erro interno na conexão")
    finally:
        await pubsub.aclose()
        await client.aclose()
