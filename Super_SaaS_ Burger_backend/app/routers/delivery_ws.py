from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect

from app.realtime.delivery_connections import delivery_connections
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
