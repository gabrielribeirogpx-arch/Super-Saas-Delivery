import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.sse import delivery_status_sse, delivery_tracking_sse
from app.models.order import Order


def test_sse_endpoint_has_proxy_safe_headers_and_format():
    async def _run_test():
        checks = iter([False, True])

        async def is_disconnected() -> bool:
            return next(checks)

        request = SimpleNamespace(
            is_disconnected=is_disconnected,
            query_params={"tenant": "tempero"},
            state=SimpleNamespace(),
        )
        response = await delivery_status_sse(request=request)

        assert response.media_type == "text/event-stream"
        assert response.headers["cache-control"] == "no-cache, no-transform"
        assert response.headers["connection"] == "keep-alive"
        assert response.headers["x-accel-buffering"] == "no"
        assert getattr(request.state, "tenant_id") == "tempero"

        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk)

        first_chunk = chunks[0]
        if isinstance(first_chunk, bytes):
            first_chunk = first_chunk.decode("utf-8")

        assert first_chunk.startswith("data: ")
        assert first_chunk.endswith("\n\n")

        payload = json.loads(first_chunk.removeprefix("data: ").strip())
        assert payload == {"tenant_id": "tempero", "status": "alive"}

    asyncio.run(_run_test())


def test_sse_endpoint_is_not_gzipped():
    async def _run_test():
        async def is_disconnected() -> bool:
            return True

        request = SimpleNamespace(
            is_disconnected=is_disconnected,
            query_params={"tenant": "tempero"},
            state=SimpleNamespace(),
        )
        response = await delivery_status_sse(request=request)

        assert response.headers.get("content-encoding") != "gzip"

    asyncio.run(_run_test())


def test_delivery_tracking_sse_streams_order_payload():
    async def _run_test():
        checks = iter([False, True])

        async def is_disconnected() -> bool:
            return next(checks)

        order = SimpleNamespace(id=42, status="OUT_FOR_DELIVERY", tenant_id=7)

        class _Query:
            def __init__(self, model):
                self.model = model

            def filter(self, *args, **kwargs):
                return self

            def filter_by(self, **kwargs):
                if self.model is Order:
                    assert kwargs == {"tracking_token": "secure-public-token"}
                return self

            def first(self):
                return order

        db = SimpleNamespace(query=lambda model: _Query(model))
        request = SimpleNamespace(
            is_disconnected=is_disconnected,
            query_params={},
            state=SimpleNamespace(),
        )

        response = await delivery_tracking_sse(tracking_token="secure-public-token", request=request, db=db)

        assert response.media_type == "text/event-stream"
        assert response.headers["cache-control"] == "no-cache, no-transform"
        assert response.headers["connection"] == "keep-alive"
        assert response.headers["x-accel-buffering"] == "no"
        assert getattr(request.state, "tenant_id") == 7

        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk)

        first_chunk = chunks[0]
        if isinstance(first_chunk, bytes):
            first_chunk = first_chunk.decode("utf-8")

        assert first_chunk.startswith("event: driver_location_update\n")
        payload = json.loads(first_chunk.split("\ndata: ", 1)[1].strip())
        assert payload == {
            "event": "driver_location_update",
            "tracking_token": "secure-public-token",
            "order_id": 42,
            "status": "OUT_FOR_DELIVERY",
            "progress": 0.0,
            "driver_lat": None,
            "driver_lng": None,
            "distance_meters": None,
            "duration_seconds": None,
        }

    asyncio.run(_run_test())


def test_delivery_tracking_sse_returns_404_when_order_not_found():
    async def _run_test():
        async def is_disconnected() -> bool:
            return True

        class _Query:
            def __init__(self, model):
                self.model = model

            def filter(self, *args, **kwargs):
                return self

            def filter_by(self, **kwargs):
                return self

            def first(self):
                return None

        db = SimpleNamespace(query=lambda model: _Query(model))
        request = SimpleNamespace(
            is_disconnected=is_disconnected,
            query_params={"tenant": "tempero"},
            state=SimpleNamespace(),
        )

        with pytest.raises(HTTPException) as exc:
            await delivery_tracking_sse(tracking_token="missing-token", request=request, db=db)

        assert exc.value.status_code == 404
        assert exc.value.detail == "Order not found"

    asyncio.run(_run_test())


def test_delivery_status_sse_requires_tenant_query_param():
    async def _run_test():
        async def is_disconnected() -> bool:
            return True

        request = SimpleNamespace(
            is_disconnected=is_disconnected,
            query_params={},
            state=SimpleNamespace(),
        )

        with pytest.raises(HTTPException) as exc:
            await delivery_status_sse(request=request)

        assert exc.value.status_code == 400
        assert exc.value.detail == "Tenant required"

    asyncio.run(_run_test())


def test_delivery_tracking_sse_streams_redis_updates(monkeypatch):
    async def _run_test():
        checks = iter([False, False, True])

        async def is_disconnected() -> bool:
            return next(checks)

        order = SimpleNamespace(id=42, status="OUT_FOR_DELIVERY", tenant_id=7)

        class _Query:
            def __init__(self, model):
                self.model = model

            def filter(self, *args, **kwargs):
                return self

            def filter_by(self, **kwargs):
                if self.model is Order:
                    assert kwargs == {"tracking_token": "secure-public-token"}
                return self

            def first(self):
                return order

        class _PubSub:
            def __init__(self):
                self.subscribed = []
                self.unsubscribed = []
                self.calls = 0

            async def subscribe(self, channel):
                self.subscribed.append(channel)

            async def unsubscribe(self, channel):
                self.unsubscribed.append(channel)

            async def aclose(self):
                return None

            async def get_message(self, **_kwargs):
                self.calls += 1
                if self.calls == 1:
                    return {"data": json.dumps({"status": "ARRIVING", "lat": -23.5, "lng": -46.6}).encode()}
                return None

        class _Redis:
            def __init__(self):
                self.pubsub_instance = _PubSub()

            def pubsub(self):
                return self.pubsub_instance

            async def aclose(self):
                return None

        redis = _Redis()
        monkeypatch.setattr("app.api.sse.get_async_redis_client", lambda: redis)

        db = SimpleNamespace(query=lambda model: _Query(model))
        request = SimpleNamespace(
            is_disconnected=is_disconnected,
            query_params={"tenant": "tempero"},
            state=SimpleNamespace(),
        )

        response = await delivery_tracking_sse(tracking_token="secure-public-token", request=request, db=db)

        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk)
            if len(chunks) >= 2:
                break

        first_chunk = chunks[0].decode("utf-8") if isinstance(chunks[0], bytes) else chunks[0]
        second_chunk = chunks[1].decode("utf-8") if isinstance(chunks[1], bytes) else chunks[1]

        assert first_chunk.startswith("event: driver_location_update\n")
        assert second_chunk.startswith("event: driver_location_update\n")
        initial_payload = json.loads(first_chunk.split("\ndata: ", 1)[1].strip())
        redis_payload = json.loads(second_chunk.split("\ndata: ", 1)[1].strip())

        assert initial_payload["order_id"] == 42
        assert redis_payload == {
            "event": "driver_location_update",
            "tracking_token": "secure-public-token",
            "order_id": 42,
            "status": "ARRIVING",
            "lat": -23.5,
            "lng": -46.6,
        }
        assert redis.pubsub_instance.subscribed == ["delivery:42"]

    asyncio.run(_run_test())
