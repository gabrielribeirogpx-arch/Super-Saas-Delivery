from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
import asyncio
import json
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.order import Order
from app.services.tenant_resolver import TenantResolver

router = APIRouter(prefix="/sse", tags=["SSE"])


@router.get("/delivery/status")
async def delivery_status_sse(request: Request):
    tenant = request.query_params.get("tenant")
    if not tenant:
        raise HTTPException(status_code=400, detail="Tenant required")

    request.state.tenant_id = tenant

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break

            payload = {
                "tenant_id": tenant,
                "status": "alive"
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


@router.get("/delivery/{order_id}")
async def delivery_tracking_sse(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    tenant = request.query_params.get("tenant")
    if not tenant:
        raise HTTPException(status_code=400, detail="Tenant required")

    resolved_tenant = TenantResolver._resolve_tenant_from_header(db, tenant)
    if resolved_tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    request.state.tenant_id = resolved_tenant.id

    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if int(order.tenant_id) != int(resolved_tenant.id):
        raise HTTPException(status_code=404, detail="Order not found")

    async def event_generator():
        progress = 0.0

        while True:
            if await request.is_disconnected():
                break

            current_order = db.get(Order, order_id)
            current_status = current_order.status if current_order else order.status

            payload = {
                "order_id": str(order_id),
                "status": current_status,
                "progress": progress,
            }
            yield f"data: {json.dumps(payload)}\n\n"

            await asyncio.sleep(2)
            progress = min(progress + 0.05, 1.0)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
