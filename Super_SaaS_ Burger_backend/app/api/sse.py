from typing import Union

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import asyncio
import json

router = APIRouter(prefix="/sse", tags=["SSE"])


@router.get("/delivery/status")
async def delivery_status_sse(request: Request, tenant_id: Union[int, str]):

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break

            payload = {
                "tenant_id": tenant_id,
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
            "Content-Encoding": "identity",
            "X-Accel-Buffering": "no",
        },
    )
