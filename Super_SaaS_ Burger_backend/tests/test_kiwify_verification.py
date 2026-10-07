from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from threading import Barrier

from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from test_billing_phase2 import database
from app.core.database import get_db
from app.core.kiwify_config import KiwifySettings, kiwify_settings
from app.models.admin_audit_log import AdminAuditLog
from app.models.billing_checkout_intent import BillingCheckoutIntent
from app.models.billing_event import BillingEvent, BillingEventStatus, BillingVerificationStatus as V
from app.models.plan import Plan
from app.models.subscription import Subscription, SubscriptionStatus as S
from app.routers.kiwify_billing import router
from app.services.billing_catalog import BillingCatalogService
from app.services.billing_inbox import BillingInboxService
from app.services.entitlements import EntitlementService
from app.services.kiwify_api import KiwifySalesAPI, VerificationOutcome, VerificationUnavailable, VerifiedSubscription
from app.services.kiwify_projection import project_webhook
from app.services.kiwify_reconciliation import schedule_reconciliation
from app.services.kiwify_verification import KiwifyVerificationService
from app.core.logging_setup import JsonFormatter

NOW = datetime(2026, 10, 6, 12, tzinfo=timezone.utc)
ORDER, SUB, PRODUCT, OFFER = [f"00000000-0000-4000-8000-{i:012d}" for i in range(1, 5)]
SETTINGS = KiwifySettings(True, "sandbox", "account-1")


def payload(event="order_approved"):
    return {"order_id": ORDER, "webhook_event_type": event, "subscription_id": SUB,
            "Product": {"product_id": PRODUCT, "product_name": "discard-me"},
            "Subscription": {"id": SUB, "plan": {"id": OFFER}, "status": "active"},
            "Customer": {"private_field": "discard-me"}, "Commissions": {"private_field": "discard-me"}}


@pytest.fixture
def sessions(tmp_path):
    engine = database(create_engine(f"sqlite:///{tmp_path / 'kiwify.db'}", connect_args={"check_same_thread": False, "timeout": 10}))
    factory = sessionmaker(bind=engine)
    yield factory
    engine.dispose()


def receive(sessions, value=None):
    value = value or payload()
    projection, identity = project_webhook(value)
    with sessions() as db, db.begin():
        return BillingInboxService(db).receive_event(provider="kiwify", environment="sandbox", provider_account_id="account-1",
            provider_event_id=identity, event_type=projection["webhook_event_type"], payload=value, schema_version=2,
            sanitized_projection=projection).event.id


@pytest.fixture
def client(sessions, monkeypatch):
    from app.routers import kiwify_billing
    from app.core.rate_limiter import InMemoryRateLimiterService
    monkeypatch.setattr(kiwify_billing, "_limiter", InMemoryRateLimiterService(limit=60))
    app = FastAPI()
    app.include_router(router)
    def dependency():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = dependency
    app.dependency_overrides[kiwify_settings] = lambda: SETTINGS
    with TestClient(app) as value:
        yield value


def test_untrusted_ingress_is_minimized_unlinked_and_never_changes_subscription(client, sessions):
    response = client.post("/api/webhooks/billing/kiwify?signature=discard-me&tenant_id=2", json=payload())
    assert response.status_code == 202
    with sessions() as db:
        event = db.query(BillingEvent).one()
        assert event.verification_status == V.PENDING and event.processing_status == BillingEventStatus.PENDING
        assert event.tenant_id is event.subscription_id is event.checkout_intent_id is None
        assert "discard-me" not in event.raw_payload
        assert db.query(Subscription).count() == 0
        assert EntitlementService(db).evaluate(1, "tracking").reason == "legacy_no_subscription"


def test_duplicate_conflict_and_distinct_type(client, sessions):
    assert client.post("/api/webhooks/billing/kiwify", json=payload()).status_code == 202
    assert client.post("/api/webhooks/billing/kiwify", json=payload()).json()["duplicate"] is True
    changed = payload()
    changed["Subscription"]["status"] = "different"
    assert client.post("/api/webhooks/billing/kiwify", json=changed).status_code == 409
    assert client.post("/api/webhooks/billing/kiwify", json=payload("refund")).status_code == 202
    with sessions() as db:
        assert db.query(BillingEvent).count() == 2


@pytest.mark.parametrize("body,media,code", [(b'{', 'application/json', 422),
    (b'{}', 'text/plain', 415), (b'x' * 65537, 'application/json', 413),
    (b'{"order_id":1,"order_id":2}', 'application/json', 422),
    (b'{"x":NaN}', 'application/json', 422)])
def test_invalid_ingress(client, sessions, body, media, code):
    assert client.post("/api/webhooks/billing/kiwify", content=body, headers={"content-type": media}).status_code == code
    with sessions() as db:
        assert db.query(BillingEvent).count() == 0


def test_disabled_ingress(client):
    client.app.dependency_overrides[kiwify_settings] = lambda: KiwifySettings()
    assert client.post("/api/webhooks/billing/kiwify", json=payload()).status_code == 404


def test_concurrent_duplicate(sessions):
    barrier = Barrier(2)
    def call():
        barrier.wait()
        return receive(sessions)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: call(), range(2)))
    assert results[0] == results[1]


def test_shared_budget_and_retry_exhaustion(sessions):
    class Offline:
        def verify(self, _):
            raise VerificationUnavailable()
    instant = [NOW]
    service = KiwifyVerificationService(sessions, SETTINGS, source=Offline(), clock=lambda: instant[0])
    service.reserve_requests()
    with pytest.raises(VerificationUnavailable):
        service.reserve_requests()
    event_id = receive(sessions)
    for attempt in range(1, 9):
        assert service.verify_event(event_id) == (V.RETRYING if attempt < 8 else V.MANUAL_REVIEW)
        if attempt < 8:
            assert service.verify_event(event_id) is None
        instant[0] += timedelta(hours=2)
    with sessions() as db:
        assert db.get(BillingEvent, event_id).verification_attempts == 8
        assert db.query(Subscription).count() == 0


def test_official_api_confirms_sale_only_not_subscription(sessions):
    calls = []
    def api(request):
        calls.append((request.method, request.url.path))
        if request.url.path.endswith("/oauth/token"):
            return httpx.Response(200, json={"access_token": "synthetic-api-token", "token_type": "Bearer", "scope": "sales", "expires_in": 86400})
        assert request.headers["x-kiwify-account-id"] == "account-1"
        return httpx.Response(200, json={"id": ORDER, "product": {"id": PRODUCT}, "status": "paid",
            "subscription": {"id": SUB, "status": "active", "plan": {"id": OFFER}}})
    source = KiwifySalesAPI(replace(SETTINGS, client_id="synthetic-client", client_secret="synthetic-secret"),
        reserve=lambda: None, transport=httpx.MockTransport(api))
    try:
        assert source.verify(project_webhook(payload())[0]).status == V.MANUAL_REVIEW
        assert source.verify(project_webhook(payload())[0]).status == V.MANUAL_REVIEW
        assert sum(path.endswith("/oauth/token") for _, path in calls) == 1
        assert all("subscriptions" not in path for _, path in calls)
    finally:
        source.close()


@pytest.mark.parametrize("status,expected", [(429, "retry"), (500, "retry"), (404, "retry"), (403, "manual")])
def test_api_failures_do_not_become_verification(status, expected):
    source = KiwifySalesAPI(replace(SETTINGS, client_id="synthetic-client", client_secret="synthetic-secret"),
        reserve=lambda: None, transport=httpx.MockTransport(lambda request: httpx.Response(status)))
    try:
        if expected == "retry":
            with pytest.raises(VerificationUnavailable):
                source.verify(project_webhook(payload())[0])
        else:
            assert source.verify(project_webhook(payload())[0]).status == V.MANUAL_REVIEW
    finally:
        source.close()


def test_sale_mismatch_rejected():
    responses = iter([{"access_token": "synthetic-token", "scope": "sales", "token_type": "Bearer", "expires_in": 86400},
                      {"id": ORDER, "product": {"id": OFFER}, "status": "paid"}])
    source = KiwifySalesAPI(replace(SETTINGS, client_id="synthetic-client", client_secret="synthetic-secret"),
        reserve=lambda: None, transport=httpx.MockTransport(lambda request: httpx.Response(200, json=next(responses))))
    try:
        assert source.verify(project_webhook(payload())[0]).status == V.REJECTED
    finally:
        source.close()


def trusted_setup(sessions, tenant_id=1):
    with sessions() as db, db.begin():
        plan = db.query(Plan).filter_by(code="essential").one()
        catalog = BillingCatalogService(db)
        catalog.create_mapping(provider="kiwify", environment="sandbox", provider_account_id="account-1",
            external_product_id=PRODUCT, external_offer_id=OFFER, plan_id=plan.id)
        intent = catalog.create_intent(tenant_id, plan.id, provider="kiwify", environment="sandbox", provider_account_id="account-1", expires_at=NOW + timedelta(hours=1), now=NOW)
        catalog.complete_intent(tenant_id, intent.public_token, external_subscription_id=SUB, now=NOW)
    return VerifiedSubscription("account-1", "sandbox", ORDER, SUB, PRODUCT, OFFER, S.ACTIVE, NOW, NOW + timedelta(days=30), NOW)


def test_trusted_source_with_internal_correlation_applies_atomically_and_once(sessions):
    proof = trusted_setup(sessions, tenant_id=2)
    class TrustedFutureSource:
        def verify(self, projection):
            return VerificationOutcome(V.VERIFIED, "trusted_subscription_confirmed", proof)
    event_id = receive(sessions)
    service = KiwifyVerificationService(sessions, SETTINGS, source=TrustedFutureSource(), clock=lambda: NOW)
    assert service.verify_event(event_id) == V.VERIFIED
    assert service.verify_event(event_id) is None
    with sessions() as db:
        sub = db.query(Subscription).one()
        assert sub.tenant_id == 2 and sub.status == S.ACTIVE
        assert db.get(BillingEvent, event_id).processing_status == BillingEventStatus.PROCESSED
        assert db.query(AdminAuditLog).count() == 3
        assert EntitlementService(db).evaluate(1, "tracking").reason == "legacy_no_subscription"


def test_verified_without_correlation_fails_closed(sessions):
    proof = trusted_setup(sessions)
    with sessions() as db, db.begin():
        db.query(BillingCheckoutIntent).delete()
    class TrustedFutureSource:
        def verify(self, _):
            return VerificationOutcome(V.VERIFIED, "trusted_subscription_confirmed", proof)
    event_id = receive(sessions)
    assert KiwifyVerificationService(sessions, SETTINGS, source=TrustedFutureSource(), clock=lambda: NOW).verify_event(event_id) == V.MANUAL_REVIEW
    with sessions() as db:
        assert db.query(Subscription).count() == db.query(AdminAuditLog).count() == 0


def test_lease_prevents_concurrent_verification(sessions):
    event_id = receive(sessions)
    entered, release = Barrier(2), Barrier(2)
    class Slow:
        def verify(self, _):
            entered.wait()
            release.wait()
            return VerificationOutcome(V.MANUAL_REVIEW, "subscription_unconfirmed")
    service = KiwifyVerificationService(sessions, SETTINGS, source=Slow(), clock=lambda: NOW)
    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(service.verify_event, event_id)
        entered.wait()
        assert service.verify_event(event_id) is None
        release.wait()
        assert future.result() == V.MANUAL_REVIEW


def test_reconciliation_is_periodic_idempotent_and_never_changes_subscription(sessions):
    with sessions() as db, db.begin():
        plan = db.query(Plan).first()
        db.add(Subscription(tenant_id=1, plan_id=plan.id, provider="kiwify", provider_subscription_id=SUB,
            status=S.ACTIVE, current_period_start=NOW, current_period_end=NOW + timedelta(days=30)))
    assert schedule_reconciliation(sessions, SETTINGS, NOW) == 1
    assert schedule_reconciliation(sessions, SETTINGS, NOW) == 0
    assert schedule_reconciliation(sessions, SETTINGS, NOW + timedelta(hours=1)) == 1
    service = KiwifyVerificationService(sessions, SETTINGS, clock=lambda: NOW)
    assert service.run_pending() == [V.MANUAL_REVIEW, V.MANUAL_REVIEW]
    with sessions() as db:
        assert db.query(Subscription).one().status == S.ACTIVE


def test_signature_redacted():
    import logging
    record = logging.LogRecord("test", logging.INFO, "", 0, "POST /api/webhooks/billing/kiwify?signature=sensitive-marker&x=1", (), None)
    assert "sensitive-marker" not in JsonFormatter().format(record)

def test_database_failure_is_not_acknowledged(client, monkeypatch):
    from sqlalchemy.exc import OperationalError
    def fail(*args, **kwargs):
        raise OperationalError("private-marker", {}, Exception("private-marker"))
    monkeypatch.setattr(BillingInboxService, "receive_event", fail)
    response = client.post("/api/webhooks/billing/kiwify", json=payload())
    assert response.status_code == 503
    assert "private-marker" not in response.text


def test_tenant_middleware_skips_untrusted_headers(client, monkeypatch):
    from app.middleware.tenant_context import TenantContextMiddleware
    from app.middleware.observability import ObservabilityMiddleware
    def forbidden():
        raise AssertionError("Tenant lookup must not happen")
    monkeypatch.setattr("app.middleware.tenant_context.SessionLocal", forbidden)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides.update(client.app.dependency_overrides)
    app.add_middleware(TenantContextMiddleware)
    app.add_middleware(ObservabilityMiddleware)
    with TestClient(app) as middleware_client:
        response = middleware_client.post("/api/webhooks/billing/kiwify?tenant_id=2", json=payload(),
            headers={"X-Tenant-ID": "2", "X-Request-ID": "discard-me"})
    assert response.status_code == 202
    assert response.headers["X-Request-ID"] != "discard-me"


@pytest.mark.parametrize("change", [
    {"account_id": "other-account"}, {"product_id": OFFER},
    {"observed_at": NOW - timedelta(minutes=6)}, {"period_end": NOW - timedelta(days=1)}])
def test_incomplete_or_mismatched_trusted_proof_cannot_activate(sessions, change):
    proof = replace(trusted_setup(sessions), **change)
    class TrustedFutureSource:
        def verify(self, _):
            return VerificationOutcome(V.VERIFIED, "trusted_subscription_confirmed", proof)
    event_id = receive(sessions)
    result = KiwifyVerificationService(sessions, SETTINGS, source=TrustedFutureSource(), clock=lambda: NOW).verify_event(event_id)
    assert result == V.MANUAL_REVIEW
    with sessions() as db:
        assert db.query(Subscription).count() == db.query(AdminAuditLog).count() == 0


def test_missing_mapping_cannot_activate(sessions):
    proof = trusted_setup(sessions)
    from app.models.billing_offer_mapping import BillingOfferMapping
    with sessions() as db, db.begin():
        db.query(BillingOfferMapping).update({"active": False})
    class TrustedFutureSource:
        def verify(self, _):
            return VerificationOutcome(V.VERIFIED, "trusted_subscription_confirmed", proof)
    event_id = receive(sessions)
    assert KiwifyVerificationService(sessions, SETTINGS, source=TrustedFutureSource(), clock=lambda: NOW).verify_event(event_id) == V.MANUAL_REVIEW
    with sessions() as db:
        assert db.query(Subscription).count() == 0


def test_stale_lease_cannot_finalize(sessions):
    event_id = receive(sessions)
    with sessions() as db, db.begin():
        event = db.get(BillingEvent, event_id)
        event.verification_lease_token = "new-lease"
        event.verification_lease_until = NOW + timedelta(minutes=1)
    service = KiwifyVerificationService(sessions, SETTINGS, clock=lambda: NOW)
    assert service._finish(event_id, "old-lease", {}, VerificationOutcome(V.REJECTED, "api_sale_reference_mismatch")) is None
    with sessions() as db:
        assert db.get(BillingEvent, event_id).verification_status == V.PENDING


def test_audit_failure_rolls_back_subscription_and_allows_lease_recovery(sessions, monkeypatch):
    proof = trusted_setup(sessions)
    class TrustedFutureSource:
        def verify(self, _):
            return VerificationOutcome(V.VERIFIED, "trusted_subscription_confirmed", proof)
    def failed_audit(*args, **kwargs):
        raise RuntimeError("synthetic-failure")
    monkeypatch.setattr("app.services.kiwify_verification.log_admin_action", failed_audit)
    event_id = receive(sessions)
    with pytest.raises(RuntimeError):
        KiwifyVerificationService(sessions, SETTINGS, source=TrustedFutureSource(), clock=lambda: NOW).verify_event(event_id)
    with sessions() as db:
        assert db.query(Subscription).count() == db.query(AdminAuditLog).count() == 0
        assert db.get(BillingEvent, event_id).verification_status == V.PENDING
    monkeypatch.undo()
    assert KiwifyVerificationService(sessions, SETTINGS, source=TrustedFutureSource(),
        clock=lambda: NOW + timedelta(minutes=3)).verify_event(event_id) == V.VERIFIED


def test_verified_renewal_uses_subscription_service_and_is_audited(sessions):
    proof = trusted_setup(sessions)
    with sessions() as db, db.begin():
        plan = db.query(Plan).filter_by(code="essential").one()
        db.add(Subscription(tenant_id=1, plan_id=plan.id, provider="kiwify", provider_subscription_id=SUB,
            status=S.ACTIVE, current_period_start=NOW - timedelta(days=30),
            current_period_end=NOW + timedelta(days=1)))
    class TrustedFutureSource:
        def verify(self, _):
            return VerificationOutcome(V.VERIFIED, "trusted_subscription_confirmed", proof)
    event_id = receive(sessions, payload("subscription_renewed"))
    assert KiwifyVerificationService(sessions, SETTINGS, source=TrustedFutureSource(), clock=lambda: NOW).verify_event(event_id) == V.VERIFIED
    with sessions() as db:
        sub = db.query(Subscription).one()
        assert sub.current_period_end.replace(tzinfo=timezone.utc) == proof.period_end
        assert sub.version == 2
        assert db.query(AdminAuditLog).filter_by(action="subscription.renewed").count() == 1

def test_local_budget_wait_does_not_exhaust_verification(sessions):
    from app.services.kiwify_api import VerificationThrottled
    class Throttled:
        def verify(self, _):
            raise VerificationThrottled()
    instant = [NOW]
    service = KiwifyVerificationService(sessions, SETTINGS, source=Throttled(), clock=lambda: instant[0])
    event_id = receive(sessions)
    for _ in range(10):
        assert service.verify_event(event_id) == V.RETRYING
        instant[0] += timedelta(seconds=3)
    with sessions() as db:
        assert db.get(BillingEvent, event_id).verification_attempts == 0
