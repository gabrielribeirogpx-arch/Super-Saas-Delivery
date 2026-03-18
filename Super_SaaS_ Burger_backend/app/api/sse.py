from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
import asyncio
import json
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.order import Order
from app.services.public_tracking import normalize_tracking_token
from app.services.tenant_resolver import TenantResolver

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
    tenant = _resolve_tenant_param(request)

    resolved_tenant = TenantResolver._resolve_tenant_from_header(db, tenant)
    if resolved_tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    request.state.tenant_id = resolved_tenant.id

    token = normalize_tracking_token(tracking_token)
    order = db.query(Order).filter_by(tracking_token=token).first()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if int(order.tenant_id) != int(resolved_tenant.id):
        raise HTTPException(status_code=404, detail="Order not found")

    async def event_generator():
        progress = 0.0

        while True:
            if await request.is_disconnected():
                break

            current_order = db.query(Order).filter_by(tracking_token=token).first()
            current_status = current_order.status if current_order else order.status

            payload = {
                "tracking_token": token,
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


# Backward-compatible alias used by some callers.
delivery_sse = delivery_tracking_sse
