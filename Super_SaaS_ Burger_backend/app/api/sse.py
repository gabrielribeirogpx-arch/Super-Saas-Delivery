from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
import asyncio
import json

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

            yield f"data: {json.dumps(payload)}\\n\\n"

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


@router.get("/sse/delivery/{order_id}")
@router.get("/api/sse/delivery/{order_id}")
async def delivery_sse(order_id: int, request: Request):
    tenant = _resolve_tenant_param(request)
    request.state.tenant_id = tenant

    async def generator():
        progress = 0.5
        while True:
            if await request.is_disconnected():
                break

            yield (
                f"data: {json.dumps({'order_id': order_id, 'status': 'OUT_FOR_DELIVERY', 'progress': progress})}\\n\\n"
            )
            progress = min(progress + 0.05, 1.0)
            await asyncio.sleep(2)

    return StreamingResponse(
        generator(),
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
            "X-Accel-Buffering": "no",
        },
    )
