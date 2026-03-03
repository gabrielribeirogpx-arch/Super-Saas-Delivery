from __future__ import annotations

import json
import logging

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


def _extract_admin_connection_claims(websocket: WebSocket) -> int:
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

    return int(tenant_id_raw)


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


@router.websocket("/ws/admin/delivery-status")
async def admin_delivery_status_ws(websocket: WebSocket):
    try:
        tenant_id = _extract_admin_connection_claims(websocket)
    except Exception as exc:
        await websocket.close(code=1008, reason=str(exc))
        return

    client = get_async_redis_client()
    if client is None:
        await websocket.close(code=1011, reason="Redis indisponível")
        return

    status_channel = f"tenant:{tenant_id}:delivery-status"
    location_channel = f"tenant:{tenant_id}:delivery-location"
    pubsub = client.pubsub()

    await websocket.accept()

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
        logger.debug("Admin delivery-status websocket disconnected tenant_id=%s", tenant_id)
    finally:
        await pubsub.aclose()
        await client.aclose()
