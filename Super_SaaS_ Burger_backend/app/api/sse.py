from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import asyncio
import json

router = APIRouter(prefix="/sse", tags=["SSE"])


@router.get("/delivery/status")
async def delivery_status_sse(request: Request, tenant_id: int):

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break

            data = {
                "tenant_id": tenant_id,
                "status": "alive"
            }

            yield f"data: {json.dumps(data)}\n\n"

            await asyncio.sleep(2)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
