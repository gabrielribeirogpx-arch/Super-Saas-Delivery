from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
import asyncio
import json
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.integrations.redis_client import get_async_redis_client
from app.models.order import Order
from app.realtime.publisher import delivery_order_channel
from app.services.public_tracking import normalize_tracking_token

router = APIRouter(tags=["SSE"])


def _resolve_tenant_param(request: Request, tenant_id: str | int | None = None) -> str:
    tenant = request.query_params.get("tenant")
    if not tenant:
        tenant = request.query_params.get("tenant_id")
    if not tenant and tenant_id is not None:
        tenant = str(tenant_id)

    if not tenant:
        raise HTTPException(status_code=400, detail="Tenant required")

    return tenant


@router.get("/sse/delivery/status")
@router.get("/api/sse/delivery/status")
async def delivery_status_sse(request: Request, tenant_id: str | int | None = None):
    tenant = _resolve_tenant_param(request, tenant_id=tenant_id)
    request.state.tenant_id = tenant

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break

            payload = {
                "tenant_id": tenant,
                "status": "alive",
            }

            yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(2)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/sse/delivery/{tracking_token}")
@router.get("/api/sse/delivery/{tracking_token}")
async def delivery_tracking_sse(
    tracking_token: str,
    request: Request,
    db: Session = Depends(get_db),
):
    token = normalize_tracking_token(tracking_token)
    order = db.query(Order).filter_by(tracking_token=token).first()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    request.state.tenant_id = int(order.tenant_id)

    channel = delivery_order_channel(int(order.id))

    async def event_generator():
        initial_payload = {
            "event": "driver_location_update",
            "tracking_token": token,
            "order_id": int(order.id),
            "status": order.status,
            "progress": 0.0,
            "driver_lat": None,
            "driver_lng": None,
            "distance_meters": None,
            "duration_seconds": None,
        }
        yield f"event: driver_location_update\ndata: {json.dumps(initial_payload)}\n\n"

        redis = get_async_redis_client()
        pubsub = redis.pubsub() if redis is not None else None
        try:
            if pubsub is not None:
                await pubsub.subscribe(channel)

            while True:
                if await request.is_disconnected():
                    break

                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0) if pubsub is not None else None
                if message is not None:
                    raw_payload = message.get("data")
                    payload_text = raw_payload.decode() if isinstance(raw_payload, bytes) else str(raw_payload)

                    try:
                        payload = json.loads(payload_text)
                    except (TypeError, json.JSONDecodeError):
                        payload = None

                    if isinstance(payload, dict):
                        payload.setdefault("event", "driver_location_update")
                        payload.setdefault("tracking_token", token)
                        payload.setdefault("order_id", int(order.id))
                        yield f"event: {payload['event']}\ndata: {json.dumps(payload)}\n\n"
                        continue

                yield ": keep-alive\n\n"
                await asyncio.sleep(1)
        finally:
            if pubsub is not None:
                await pubsub.unsubscribe(channel)
                await pubsub.aclose()
            if redis is not None:
                await redis.aclose()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# Backward-compatible alias used by some callers.
delivery_sse = delivery_tracking_sse
