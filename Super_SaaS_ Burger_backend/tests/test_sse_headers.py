import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.sse import delivery_status_sse, delivery_tracking_sse


def test_sse_endpoint_has_proxy_safe_headers_and_format():
    async def _run_test():
        checks = iter([False, True])

        async def is_disconnected() -> bool:
            return next(checks)

        request = SimpleNamespace(is_disconnected=is_disconnected)
        response = await delivery_status_sse(request=request, tenant_id=9)

        assert response.media_type == "text/event-stream"
        assert response.headers["cache-control"] == "no-cache, no-transform"
        assert response.headers["connection"] == "keep-alive"
        assert response.headers["x-accel-buffering"] == "no"
        assert response.headers["content-encoding"] == "identity"

        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk)

        first_chunk = chunks[0]
        if isinstance(first_chunk, bytes):
            first_chunk = first_chunk.decode("utf-8")

        assert first_chunk.startswith("data: ")
        assert first_chunk.endswith("\n\n")

        payload = json.loads(first_chunk.removeprefix("data: ").strip())
        assert payload == {"tenant_id": 9, "status": "alive"}

    asyncio.run(_run_test())


def test_sse_endpoint_is_not_gzipped():
    async def _run_test():
        async def is_disconnected() -> bool:
            return True

        request = SimpleNamespace(is_disconnected=is_disconnected)
        response = await delivery_status_sse(request=request, tenant_id=1)

        assert response.headers.get("content-encoding") != "gzip"

    asyncio.run(_run_test())


def test_delivery_tracking_sse_streams_order_payload():
    async def _run_test():
        checks = iter([False, True])

        async def is_disconnected() -> bool:
            return next(checks)

        order = SimpleNamespace(status="OUT_FOR_DELIVERY")
        db = SimpleNamespace(get=lambda model, order_id: order)
        request = SimpleNamespace(is_disconnected=is_disconnected)

        response = await delivery_tracking_sse(order_id=42, request=request, db=db)

        assert response.media_type == "text/event-stream"
        assert response.headers["cache-control"] == "no-cache, no-transform"
        assert response.headers["connection"] == "keep-alive"
        assert response.headers["x-accel-buffering"] == "no"
        assert response.headers["content-encoding"] == "identity"

        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk)

        first_chunk = chunks[0]
        if isinstance(first_chunk, bytes):
            first_chunk = first_chunk.decode("utf-8")

        payload = json.loads(first_chunk.removeprefix("data: ").strip())
        assert payload == {
            "order_id": "42",
            "status": "OUT_FOR_DELIVERY",
            "progress": 0.0,
        }

    asyncio.run(_run_test())


def test_delivery_tracking_sse_returns_404_when_order_not_found():
    async def _run_test():
        async def is_disconnected() -> bool:
            return True

        db = SimpleNamespace(get=lambda model, order_id: None)
        request = SimpleNamespace(is_disconnected=is_disconnected)

        with pytest.raises(HTTPException) as exc:
            await delivery_tracking_sse(order_id=999, request=request, db=db)

        assert exc.value.status_code == 404
        assert exc.value.detail == "Order not found"

    asyncio.run(_run_test())
