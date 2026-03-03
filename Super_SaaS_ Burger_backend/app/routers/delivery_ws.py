from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect

from app.integrations.redis_client import get_async_redis_client
from app.realtime.delivery_connections import delivery_connections
from app.realtime.publisher import publish_delivery_status_event
from app.services.admin_auth import ADMIN_SESSION_COOKIE, decode_admin_session
from app.services.auth import decode_access_token

logger = logging.getLogger(__name__)
router = APIRouter(tags=["delivery-realtime"])


def _extract_ws_token(websocket: WebSocket) -> str | None:
    token = websocket.query_params.get("token")
    if token:
        return token

    auth_header = websocket.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()

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


@router.websocket("/ws/delivery")
async def delivery_ws(websocket: WebSocket):
    token = _extract_ws_token(websocket)
    if not token:
        await websocket.close(code=1008, reason="Token ausente")
        return

    try:
        tenant_id, delivery_user_id = _extract_connection_claims(token)
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

    try:
        await websocket.accept()
    except Exception as exc:
        logger.exception("event=delivery_location_ws_accept_failed client=%s error=%s", client_host, exc)
        return

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

        redis_client = get_async_redis_client()
        if redis_client is None:
            raise RuntimeError("Redis indisponível")

        channel = f"tenant:{tenant_id}:delivery:locations"
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

            message = {
                "tenant_id": tenant_id,
                "delivery_user_id": delivery_user_id,
                "lat": lat,
                "lng": lng,
                "status": status,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            await redis_client.publish(channel, json.dumps(message))
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

    client = get_async_redis_client()
    if client is None:
        logger.error(
            "event=admin_delivery_ws_redis_unavailable tenant_id=%s client=%s",
            tenant_id,
            client_host,
        )
        await websocket.close(code=1011, reason="Redis indisponível")
        return

    status_channel = f"tenant:{tenant_id}:delivery-status"
    location_channel = f"tenant:{tenant_id}:delivery-location"
    pubsub = client.pubsub()

    logger.info(
        "event=admin_delivery_ws_connection_authenticated tenant_id=%s status_channel=%s location_channel=%s client=%s",
        tenant_id,
        status_channel,
        location_channel,
        client_host,
    )

    try:
        await pubsub.subscribe(status_channel, location_channel)
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message is None:
                continue

            raw_payload = message.get("data")
            payload_text = raw_payload.decode() if isinstance(raw_payload, bytes) else str(raw_payload)

            try:
                payload_data = json.loads(payload_text)
            except (TypeError, json.JSONDecodeError):
                payload_data = {"raw": payload_text}

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
