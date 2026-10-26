"""Actual PostgreSQL constraints, MVCC, leases and authenticated review paths."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
import json

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx
import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from app.core.database import Base, get_db
from app.core.kiwify_config import KiwifySettings, kiwify_settings
from app.models.admin_audit_log import AdminAuditLog
from app.models.admin_user import AdminUser
from app.models.billing_event import BillingEvent, BillingVerificationStatus as V
from app.models.billing_manual_review import BillingManualReview
from app.models.plan import Plan
from app.models.plan_entitlement import PlanEntitlement
from app.models.subscription import Subscription, SubscriptionStatus as S
from app.routers import admin_billing_reviews, kiwify_billing
from app.services.admin_auth import create_admin_session
from app.services.billing_catalog import BillingCatalogService
from app.services.billing_common import BillingConflict
from app.services.billing_inbox import BillingInboxService
from app.services.billing_manual_review import BillingManualReviewService
from app.services.entitlements import EntitlementService
from app.services.kiwify_api import KiwifySalesAPI, VerificationOutcome, VerificationUnavailable
from app.services.kiwify_projection import project_webhook
from app.services.kiwify_verification import KiwifyVerificationService
from app.services.plan_seed import seed_plans
from app.services.subscriptions import SubscriptionActor, SubscriptionService

from conftest import BASELINE, HEAD, BILLING_TABLES

NOW = datetime.now(timezone.utc)
ORDER, SUB, PRODUCT, OFFER = [f"00000000-0000-4000-8000-{i:012d}" for i in range(1, 5)]
SETTINGS = KiwifySettings(True, "sandbox", "phase4-account", "synthetic-client", "synthetic-secret")


def payload():
    return {"order_id": ORDER, "webhook_event_type": "order_approved", "subscription_id": SUB,
        "Product": {"product_id": PRODUCT}, "Subscription": {"id": SUB, "plan": {"id": OFFER}},
        "Customer": {"email": "phase4-private-marker", "phone": "phase4-private-marker"}}


def receive(sessions):
    data = payload()
    projection, identity = project_webhook(data)
    with sessions() as db, db.begin():
        return BillingInboxService(db).receive_event(provider="kiwify", environment="sandbox", provider_account_id=SETTINGS.account_id,
            provider_event_id=identity, event_type="order_approved", payload=data, schema_version=2,
            sanitized_projection=projection).event.id


def correlate(sessions, tenant_id=1):
    with sessions() as db, db.begin():
        plan = db.query(Plan).filter_by(code="essential").one()
        svc = BillingCatalogService(db)
        svc.create_mapping(provider="kiwify", environment="sandbox", provider_account_id=SETTINGS.account_id,
            external_product_id=PRODUCT, external_offer_id=OFFER, plan_id=plan.id)
        intent = svc.create_intent(tenant_id, plan.id, provider="kiwify", environment="sandbox",
            provider_account_id=SETTINGS.account_id, expires_at=NOW + timedelta(hours=1), now=NOW)
        svc.complete_intent(tenant_id, intent.public_token, external_subscription_id=SUB, now=NOW)


def source(clock=lambda: NOW):
    def api(request):
        if request.url.path.endswith("/oauth/token"):
            return httpx.Response(200, json={"access_token": "synthetic-token", "scope": "sales", "token_type": "Bearer", "expires_in": 86400})
        return httpx.Response(200, json={"id": ORDER, "status": "paid", "product": {"id": PRODUCT},
            "Customer": {"email": "phase4-private-marker"}})
    return KiwifySalesAPI(SETTINGS, reserve=lambda: None, transport=httpx.MockTransport(api), clock=clock)


def manual(sessions, tenant_id=1):
    correlate(sessions, tenant_id)
    event_id = receive(sessions)
    api = source()
    try:
        assert KiwifyVerificationService(sessions, SETTINGS, source=api, clock=lambda: NOW).verify_event(event_id) == V.MANUAL_REVIEW
    finally:
        api.close()
    return event_id


def client(sessions, user_id=1):
    app = FastAPI()
    app.include_router(admin_billing_reviews.router)
    app.include_router(kiwify_billing.router)
    def database():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = database
    app.dependency_overrides[kiwify_settings] = lambda: SETTINGS
    value = TestClient(app, headers={"X-Billing-Review": "1"})
    # Real signed cookie and AuthService; no authentication/RBAC bypass.
    with sessions() as db:
        user = db.get(AdminUser, user_id)
        value.cookies.set("admin_session", create_admin_session({"user_id": user.id, "tenant_id": user.tenant_id}))
    return value


def test_billing_migration_roundtrip_schema_constraints_and_seed(pg):
    engine, cfg, sessions = pg
    assert ScriptDirectory.from_config(cfg).get_heads() == [HEAD]
    def include(obj, name, kind, reflected, compared):
        table = obj if kind == "table" else getattr(obj, "table", None)
        return table is None or table.name in BILLING_TABLES
    with engine.connect() as conn:
        assert compare_metadata(MigrationContext.configure(conn, opts={"include_object": include, "compare_type": True}), Base.metadata) == []
    inspector = sa.inspect(engine)
    assert "uq_billing_event_identity" in {x["name"] for x in inspector.get_unique_constraints("billing_events")}
    assert "fk_billing_event_subscription_tenant" in {x["name"] for x in inspector.get_foreign_keys("billing_events")}
    assert "ix_billing_events_verification_status" in {x["name"] for x in inspector.get_indexes("billing_events")}
    with sessions() as db, db.begin():
        seed_plans(db)
        assert db.query(Plan).count() == 3
        assert db.query(PlanEntitlement).count() == 30
    command.downgrade(cfg, BASELINE)
    assert not (BILLING_TABLES & set(sa.inspect(engine).get_table_names()))
    command.upgrade(cfg, HEAD)
    with sessions() as db:
        assert db.query(AdminUser).count() == 3


def test_end_to_end_cookie_auth_without_presumed_period(pg):
    _, _, sessions = pg
    correlate(sessions)
    with client(sessions) as http:
        response = http.post("/api/webhooks/billing/kiwify?signature=phase4-private-marker", json=payload())
        assert response.status_code == 202
        with sessions() as db:
            event_id = db.query(BillingEvent).one().id
            assert db.query(Subscription).count() == 0
        api = source()
        try:
            assert KiwifyVerificationService(sessions, SETTINGS, source=api, clock=lambda: NOW).verify_event(event_id) == V.MANUAL_REVIEW
        finally:
            api.close()
        listed = http.get("/api/admin/billing/reviews")
        assert listed.status_code == 200 and len(listed.json()) == 1
        assert "phase4-private-marker" not in listed.text
        approved = http.post(f"/api/admin/billing/reviews/{event_id}/approve")
        assert approved.status_code == 200 and approved.json()["decision"] == "binding_approved"
    with sessions() as db:
        sub = db.query(Subscription).one()
        assert sub.status == S.INACTIVE and sub.current_period_start is sub.current_period_end is None
        assert not EntitlementService(db).evaluate(1, "orders_monthly").allowed
        event = db.get(BillingEvent, event_id)
        assert event.verification_error_code == "manual_review_period_missing" and event.verification_status == V.MANUAL_REVIEW
        audit = db.query(AdminAuditLog).filter_by(action="billing.manual_review_binding_approved").one()
        assert audit.tenant_id == 1 and audit.user_id == 1 and audit.actor_type == "user"


def test_duplicate_and_concurrent_receipt(pg):
    _, _, sessions = pg
    first = receive(sessions)
    assert receive(sessions) == first
    barrier = Barrier(2)
    def ingest():
        barrier.wait()
        return receive(sessions)
    with ThreadPoolExecutor(2) as pool:
        assert list(pool.map(lambda _: ingest(), range(2))) == [first, first]
    with sessions() as db:
        assert db.query(BillingEvent).count() == 1


def test_simultaneous_human_approvals(pg):
    _, _, sessions = pg
    event_id = manual(sessions)
    barrier = Barrier(2)
    def approve():
        with sessions() as db:
            user = db.get(AdminUser, 1)
            barrier.wait()
            try:
                BillingManualReviewService(db, clock=lambda: NOW).decide(event_id, user, approve=True)
                db.commit()
                return "approved"
            except BillingConflict:
                db.rollback()
                return "conflict"
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(lambda _: approve(), range(2))) == ["approved", "conflict"]
    with sessions() as db:
        assert db.query(Subscription).count() == 1
        assert db.query(AdminAuditLog).filter_by(action="billing.manual_review_binding_approved").count() == 1


def test_two_workers_and_expired_lease(pg):
    _, _, sessions = pg
    event_id = receive(sessions)
    entered, release = Barrier(2), Barrier(2)
    class Slow:
        def verify(self, _):
            entered.wait()
            release.wait()
            return VerificationOutcome(V.MANUAL_REVIEW, "subscription_endpoint_unconfirmed")
    service = KiwifyVerificationService(sessions, SETTINGS, source=Slow(), clock=lambda: NOW)
    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(service.verify_event, event_id)
        entered.wait()
        assert service.verify_event(event_id) is None
        release.wait()
        assert future.result() == V.MANUAL_REVIEW
    with sessions() as db, db.begin():
        event = db.get(BillingEvent, event_id)
        event.verification_status = V.PENDING
        event.verification_lease_token = "expired-lease"
        event.verification_lease_until = NOW - timedelta(minutes=1)
    class Ready:
        def verify(self, _):
            return VerificationOutcome(V.MANUAL_REVIEW, "subscription_endpoint_unconfirmed")
    service = KiwifyVerificationService(sessions, SETTINGS, source=Ready(), clock=lambda: NOW)
    assert service.verify_event(event_id) == V.MANUAL_REVIEW
    assert service._finish(event_id, "expired-lease", {}, VerificationOutcome(V.REJECTED, "stale")) is None


def test_retry_after_provider_failure(pg):
    _, _, sessions = pg
    event_id = receive(sessions)
    instant = [NOW]
    class Flaky:
        def verify(self, _):
            if instant[0] == NOW:
                raise VerificationUnavailable()
            return VerificationOutcome(V.MANUAL_REVIEW, "subscription_endpoint_unconfirmed")
    service = KiwifyVerificationService(sessions, SETTINGS, source=Flaky(), clock=lambda: instant[0])
    assert service.verify_event(event_id) == V.RETRYING
    assert service.verify_event(event_id) is None
    instant[0] += timedelta(minutes=1)
    assert service.verify_event(event_id) == V.MANUAL_REVIEW


def test_two_current_subscriptions_for_same_tenant(pg):
    _, _, sessions = pg
    barrier = Barrier(2)
    def create():
        with sessions() as db:
            plan = db.query(Plan).filter_by(code="essential").one()
            barrier.wait()
            try:
                SubscriptionService(db).create_subscription(1, plan.id, actor=SubscriptionActor("system"))
                db.commit()
                return "created"
            except BillingConflict:
                db.rollback()
                return "conflict"
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(lambda _: create(), range(2))) == ["conflict", "created"]


def test_tenant_isolation_unknown_receipt_rbac_and_reject(pg):
    _, _, sessions = pg
    event_id = manual(sessions, tenant_id=2)
    with client(sessions, 1) as a, client(sessions, 2) as b, client(sessions, 3) as operator:
        assert a.get("/api/admin/billing/reviews").json() == []
        assert a.get(f"/api/admin/billing/reviews/{event_id}").status_code == 404
        assert a.post(f"/api/admin/billing/reviews/{event_id}/approve").status_code == 404
        assert a.post(f"/api/admin/billing/reviews/{event_id}/reject", json={"reason": "invalid_sale"}).status_code == 404
        assert operator.get("/api/admin/billing/reviews").status_code == 403
        assert b.post(f"/api/admin/billing/reviews/{event_id}/reject", json={"reason": "invalid_sale"}).status_code == 200
    with sessions() as db:
        audit = db.query(AdminAuditLog).one()
        assert audit.tenant_id == 2 and audit.user_id == 2
        assert db.get(BillingEvent, event_id) is not None
    # Remove correlation from a separate, unchanged untrusted receipt.
    with sessions() as db, db.begin():
        review = db.get(BillingManualReview, event_id)
        review.external_subscription_id = None
        event = db.get(BillingEvent, event_id)
        event.verification_status = V.MANUAL_REVIEW
    with client(sessions, 1) as a:
        assert a.get("/api/admin/billing/reviews").json() == []


def test_fk_unique_and_history_downgrade_guards(pg):
    engine, cfg, sessions = pg
    event_id = manual(sessions)
    with sessions() as db:
        with pytest.raises(IntegrityError), db.begin_nested():
            db.add(Subscription(tenant_id=999999, plan_id=1))
            db.flush()
        with pytest.raises(IntegrityError), db.begin_nested():
            db.add(Plan(code="essential", name="Duplicate"))
            db.flush()
        with pytest.raises(IntegrityError), db.begin_nested():
            db.execute(sa.text("UPDATE billing_manual_reviews SET decision='approved' WHERE billing_event_id=:id"), {"id": event_id})
    with pytest.raises(RuntimeError, match="Archive billing manual reviews"):
        command.downgrade(cfg, "20261007_01_billing_verification")
    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one() == HEAD


def test_verification_downgrade_guard_rolls_back_ddl(pg):
    engine, cfg, sessions = pg
    receive(sessions)  # schema v2 receipt, no manual review row yet
    with pytest.raises(RuntimeError, match="Archive Kiwify verification receipts"):
        command.downgrade(cfg, "20261006_07_billing_audit")
    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one() == HEAD
        assert "billing_manual_reviews" in sa.inspect(conn).get_table_names()


def test_automatic_audit_prevents_unsafe_downgrade(pg):
    engine, cfg, sessions = pg
    command.downgrade(cfg, "20261006_07_billing_audit")
    with sessions() as db:
        plan = db.query(Plan).filter_by(code="essential").one()
        SubscriptionService(db).create_subscription(1, plan.id)
        db.commit()
    with pytest.raises(RuntimeError, match="Archive automatic audit records"):
        command.downgrade(cfg, "20261006_03_subscriptions")
    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one() == "20261006_07_billing_audit"
    command.upgrade(cfg, HEAD)
