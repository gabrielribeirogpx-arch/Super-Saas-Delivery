from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.metrics import InMemoryRequestMetrics
from app.core.rate_limiter import InMemoryRateLimiterService
from app.middleware.tenant_rate_limit import TenantRateLimitMiddleware
from app.services.tenant_backoff import InMemoryTenantBackoffService


def test_rate_limit_is_isolated_per_tenant() -> None:
    service = InMemoryRateLimiterService(limit=2, window_seconds=60)

    first_tenant_a = service.check(tenant_id="tenant-a", endpoint="/orders")
    second_tenant_a = service.check(tenant_id="tenant-a", endpoint="/orders")
    blocked_tenant_a = service.check(tenant_id="tenant-a", endpoint="/orders")

    tenant_b_still_allowed = service.check(tenant_id="tenant-b", endpoint="/orders")

    assert first_tenant_a.allowed is True
    assert second_tenant_a.allowed is True
    assert blocked_tenant_a.allowed is False
    assert tenant_b_still_allowed.allowed is True


def test_middleware_returns_429_only_when_limit_exceeded() -> None:
    limiter = InMemoryRateLimiterService(limit=1, window_seconds=60)
    app = FastAPI()
    app.add_middleware(TenantRateLimitMiddleware, rate_limiter=limiter)

    @app.get("/health")
    def health():
        return {"ok": True}

    with TestClient(app) as client:
        ok = client.get("/health", headers={"X-Tenant-ID": "10"})
        blocked = client.get("/health", headers={"X-Tenant-ID": "10"})

    assert ok.status_code == 200
    assert blocked.status_code == 429


def test_metrics_snapshot_per_tenant() -> None:
    metrics = InMemoryRequestMetrics()

    metrics.observe(endpoint="/orders", method="GET", status_code=200, duration_ms=10, tenant_id="1")
    metrics.observe(endpoint="/orders", method="GET", status_code=500, duration_ms=30, tenant_id="1")
    metrics.observe(endpoint="/menu", method="GET", status_code=200, duration_ms=20, tenant_id="2")

    snapshot = metrics.snapshot_per_tenant()

    assert snapshot["1"]["requests_por_tenant"] == 2
    assert snapshot["1"]["erros_por_tenant"] == 1
    assert snapshot["1"]["latencia_media_por_tenant"] == 20.0
    assert snapshot["2"]["requests_por_tenant"] == 1


def test_backoff_is_activated_after_threshold() -> None:
    service = InMemoryTenantBackoffService(threshold=2, max_backoff_seconds=8.0)

    no_backoff = service.before_request(tenant_id=77, integration="whatsapp_cloud")
    assert no_backoff.delay_seconds == 0.0

    service.register_failure(tenant_id=77, integration="whatsapp_cloud")
    still_no_backoff = service.before_request(tenant_id=77, integration="whatsapp_cloud")
    assert still_no_backoff.delay_seconds == 0.0

    service.register_failure(tenant_id=77, integration="whatsapp_cloud")
    with_backoff = service.before_request(tenant_id=77, integration="whatsapp_cloud")
    assert with_backoff.delay_seconds >= 1.0

    service.register_success(tenant_id=77, integration="whatsapp_cloud")
    reset = service.before_request(tenant_id=77, integration="whatsapp_cloud")
    assert reset.delay_seconds == 0.0
