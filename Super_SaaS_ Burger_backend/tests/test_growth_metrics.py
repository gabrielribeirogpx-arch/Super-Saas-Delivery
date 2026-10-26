from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.core.metrics import InMemoryRequestMetrics
from app.middleware import observability


def test_request_ids_and_random_missing_urls_do_not_create_metric_series(monkeypatch):
    metrics = InMemoryRequestMetrics()
    monkeypatch.setattr(observability, "request_metrics", metrics)
    app = FastAPI()
    app.add_middleware(observability.ObservabilityMiddleware)
    @app.get("/example/{item_id}")
    def item(item_id: int):
        return {"id": item_id}
    with TestClient(app) as client:
        for i in range(10):
            assert client.get(f"/example/{i}").status_code == 200
            assert client.get(f"/random-missing-{i}").status_code == 404
    result = metrics.snapshot()
    assert set(result) == {"GET /example/{item_id}", "GET <unmatched>"}
    assert result["GET /example/{item_id}"]["total_requests"] == 10
    assert result["GET <unmatched>"]["total_requests"] == 10


def test_metric_storage_has_a_bound_and_preserves_overflow_totals():
    metrics = InMemoryRequestMetrics(max_endpoints=2, max_tenants=2)
    for i in range(100):
        metrics.observe(f"/unique/{i}", "GET", 200, 1, str(i))
    endpoints, tenants = metrics.snapshot(), metrics.snapshot_per_tenant()
    assert len(endpoints) <= 3 and len(tenants) <= 3
    assert sum(value["total_requests"] for value in endpoints.values()) == 100
    assert sum(value["requests_por_tenant"] for value in tenants.values()) == 100
