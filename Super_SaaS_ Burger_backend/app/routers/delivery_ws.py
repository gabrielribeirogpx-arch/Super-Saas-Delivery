from __future__ import annotations

import json
import logging

from fastapi import APIRouter, WebSocket
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from app.core.database import SessionLocal
from app.integrations.redis_client import get_async_redis_client
from app.models.user import User
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


def _resolve_delivery_user(token: str) -> User | None:
    payload = decode_access_token(token)
    raw_user_id = payload.get("sub") or payload.get("user_id")
    if raw_user_id is None:
        return None

    user_id = int(raw_user_id)
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        return user
    finally:
        db.close()


@router.websocket("/ws/delivery")
async def delivery_ws(websocket: WebSocket):
    token = _extract_ws_token(websocket)
    if not token:
        await websocket.close(code=1008, reason="Token ausente")
        return

    try:
        user = _resolve_delivery_user(token)
    except Exception:
        await websocket.close(code=1008, reason="Token inválido")
        return

    if not user:
        await websocket.close(code=1008, reason="Usuário não encontrado")
        return

    role = str(getattr(user, "role", "") or "").upper()
    if role != "DELIVERY":
        await websocket.close(code=1008, reason="Acesso permitido apenas para DELIVERY")
        return

    tenant_id = getattr(user, "tenant_id", None)
    if tenant_id is None:
        await websocket.close(code=1008, reason="Usuário sem tenant")
        return

    redis_client = get_async_redis_client()
    if redis_client is None:
        await websocket.close(code=1013, reason="Realtime indisponível")
        return

    await websocket.accept()
    pubsub = redis_client.pubsub()
    channel = f"tenant:{int(tenant_id)}:delivery"

    try:
        await pubsub.subscribe(channel)
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
        logger.debug("Delivery websocket disconnected tenant_id=%s", tenant_id)
    finally:
        await pubsub.aclose()
        await redis_client.aclose()
