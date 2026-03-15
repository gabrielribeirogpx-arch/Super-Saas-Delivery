from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db
from app.deps import get_current_delivery_user
from app.integrations.redis_client import get_async_redis_client
from app.models.admin_user import AdminUser
from app.models.order import Order
from app.modules.tracking.schemas import DriverLocationIn
from app.modules.tracking.service import (
    TrackingStoreError,
    can_accept_location_update,
    get_driver_location,
    save_driver_location,
)

router = APIRouter(tags=["tracking"])
logger = logging.getLogger(__name__)

OUT_FOR_DELIVERY_STATUSES = {"OUT_FOR_DELIVERY", "SAIU", "SAIU_PARA_ENTREGA"}
DELIVERED_STATUSES = {"DELIVERED", "ENTREGUE"}
POLL_SECONDS = 1.0


@router.post("/driver/location")
async def post_driver_location(
    payload: DriverLocationIn,
    db: Session = Depends(get_db),
    current_driver: AdminUser = Depends(get_current_delivery_user),
):
    tenant_id = int(current_driver.tenant_id)
    driver_id = int(current_driver.id)

    order = db.query(Order).filter(Order.id == int(payload.order_id), Order.tenant_id == tenant_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")

    if int(order.assigned_delivery_user_id or 0) != driver_id:
        raise HTTPException(status_code=409, detail="Pedido atribuído para outro motorista")

    redis = get_async_redis_client()
    if redis is None:
        raise HTTPException(status_code=503, detail="Redis indisponível")

    try:
        accepted = await can_accept_location_update(redis, order_id=int(order.id), driver_id=driver_id)
        if not accepted:
            return {"ok": True, "throttled": True}

        location = await save_driver_location(
            redis,
            order_id=int(order.id),
            lat=payload.lat,
            lng=payload.lng,
        )
    except TrackingStoreError:
        logger.exception(
            "tracking location update failed tenant_id=%s order_id=%s driver_id=%s",
            tenant_id,
            payload.order_id,
            driver_id,
        )
        raise HTTPException(status_code=500, detail="Falha ao atualizar rastreamento")
    finally:
        await redis.aclose()

    return {
        "ok": True,
        "throttled": False,
        "location": location,
    }


def _resolve_order_by_tracking_token(db: Session, order_token: str) -> Order | None:
    token = str(order_token).strip()
    if not token:
        return None
    return db.query(Order).filter(Order.tracking_token == token).first()


def _is_out_for_delivery(status: str | None) -> bool:
    return (status or "").upper() in OUT_FOR_DELIVERY_STATUSES


def _is_delivered(status: str | None) -> bool:
    return (status or "").upper() in DELIVERED_STATUSES


@router.get("/sse/order/{order_token}")
async def stream_order_tracking(order_token: str, request: Request):
    db = SessionLocal()
    try:
        order = _resolve_order_by_tracking_token(db, order_token)
        if order is None:
            raise HTTPException(status_code=404, detail="Pedido não encontrado")
        order_id = int(order.id)
    finally:
        db.close()

    redis = get_async_redis_client()
    if redis is None:
        raise HTTPException(status_code=503, detail="Redis indisponível")

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            while True:
                if await request.is_disconnected():
                    break

                loop_db = SessionLocal()
                try:
                    current_status = (
                        loop_db.query(Order.status)
                        .filter(Order.id == order_id)
                        .scalar()
                    )
                finally:
                    loop_db.close()

                if _is_delivered(current_status):
                    ended_payload = {"type": "tracking_ended"}
                    yield f"data: {json.dumps(ended_payload)}\n\n"
                    break

                if _is_out_for_delivery(current_status):
                    try:
                        location_payload = await get_driver_location(redis, order_id=order_id)
                    except TrackingStoreError:
                        logger.exception("tracking sse load failed order_id=%s", order_id)
                        yield "event: error\ndata: {\"detail\":\"tracking_unavailable\"}\n\n"
                        await asyncio.sleep(POLL_SECONDS)
                        continue

                    if location_payload is not None:
                        yield f"data: {json.dumps(location_payload)}\n\n"

                await asyncio.sleep(POLL_SECONDS)
        finally:
            await redis.aclose()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "Content-Encoding": "identity",
            "X-Accel-Buffering": "no",
        },
    )
