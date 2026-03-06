import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.tenant import Tenant
from app.services.tenant_resolver import TenantResolver

router = APIRouter(prefix="/sse", tags=["SSE"])
logger = logging.getLogger(__name__)


@router.get("/delivery/status")
async def delivery_status_sse(
    request: Request,
    tenant_id: str | None = None,
    db: Session = Depends(get_db),
):
    resolved_tenant_id = TenantResolver.resolve_tenant_id_from_request(request)

    if resolved_tenant_id is None and tenant_id is not None:
        try:
            resolved_tenant_id = int(tenant_id)
        except (TypeError, ValueError):
            tenant = db.query(Tenant).filter(Tenant.slug == str(tenant_id).strip().lower()).first()
            if tenant is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="tenant_id inválido. Informe X-Tenant-ID ou tenant_id válido.",
                )
            resolved_tenant_id = int(tenant.id)

    if resolved_tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="tenant_id ausente. Informe X-Tenant-ID ou tenant_id válido.",
        )

    logger.info("tenant resolved tenant_id=%s", resolved_tenant_id)

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break

            payload = {
                "tenant_id": int(resolved_tenant_id),
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
            "Content-Encoding": "identity",
            "X-Accel-Buffering": "no",
        },
    )
