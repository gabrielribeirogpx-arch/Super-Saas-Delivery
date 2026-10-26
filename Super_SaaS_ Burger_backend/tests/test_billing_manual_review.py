from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
import json

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest

from test_kiwify_verification import sessions, receive, trusted_setup, payload, NOW, SETTINGS, ORDER, SUB, PRODUCT, OFFER
from app.core.database import get_db
from app.deps import require_admin_user
from app.models.admin_user import AdminUser
from app.models.admin_audit_log import AdminAuditLog
from app.models.billing_event import BillingEvent, BillingEventStatus as P, BillingVerificationStatus as V
from app.models.billing_manual_review import BillingManualReview
from app.models.billing_checkout_intent import BillingCheckoutIntent
from app.models.billing_offer_mapping import BillingOfferMapping
from app.models.subscription import Subscription, SubscriptionStatus as S
from app.routers import admin_billing_reviews as routes
from app.services.billing_common import BillingConflict
from app.services.billing_manual_review import BillingManualReviewService
from app.services.entitlements import EntitlementService
from app.services.kiwify_api import VerificationOutcome, VerifiedSale
from app.services.kiwify_verification import KiwifyVerificationService

ROOT = "/api/admin/billing/reviews"


def prepare(sessions, *, period=False, tenant_id=1):
    proof = trusted_setup(sessions, tenant_id=tenant_id)
    event_id = receive(sessions)
    class OfficialEvidence:
        def verify(self, _):
            return VerificationOutcome(V.MANUAL_REVIEW, "sale_confirmed_subscription_unconfirmed",
                subscription=proof if period else None,
                sale=VerifiedSale("account-1", "sandbox", ORDER, PRODUCT, "paid", NOW))
    assert KiwifyVerificationService(sessions, SETTINGS, source=OfficialEvidence(), clock=lambda: NOW).verify_event(event_id) == V.MANUAL_REVIEW
    return event_id, proof


@pytest.fixture
def client(sessions, monkeypatch):
    app = FastAPI()
    app.include_router(routes.router)
    def database():
        with sessions() as db:
            yield db
    def actor():
        with sessions() as db:
            return db.get(AdminUser, 1)
    app.dependency_overrides[get_db] = database
    app.dependency_overrides[require_admin_user] = actor
    monkeypatch.setattr(routes, "BillingManualReviewService", lambda db: BillingManualReviewService(db, clock=lambda: NOW))
    with TestClient(app, headers={"X-Billing-Review": "1"}) as value:
        yield value


def test_list_detail_filters_and_safe_evidence(client, sessions):
    event_id, _ = prepare(sessions)
    with sessions() as db, db.begin():
        event = db.get(BillingEvent, event_id)
        receipt = json.loads(event.raw_payload)
        receipt["Customer"] = {"email": "PRIVATE_MARKER", "phone": "PRIVATE_MARKER"}
        receipt["signature"] = "PRIVATE_MARKER"
        event.raw_payload = json.dumps(receipt)
    listing = client.get(ROOT)
    assert listing.status_code == 200
    row = listing.json()[0]
    assert row["billing_event_id"] == event_id
    assert row["candidate_tenant_id"] == 1 and row["candidate_plan_name"] == "Essencial"
    assert row["sale_status"] == "paid" and row["can_approve"] and row["access_pending_period"]
    assert client.get(f"{ROOT}?event_type=refund").json() == []
    assert client.get(f"{ROOT}?plan_id=999").json() == []
    assert client.get(f"{ROOT}?offset=1").json() == []
    detail = client.get(f"{ROOT}/{event_id}")
    assert detail.status_code == 200 and detail.json() == row
    for response in [listing, detail]:
        assert "PRIVATE_MARKER" not in response.text
        assert not set(response.json()[0] if isinstance(response.json(), list) else response.json()) & {
            "raw_payload", "payload", "email", "phone", "document", "address", "signature", "token", "customer"}


@pytest.mark.parametrize("role", ["operator", "cashier", "delivery"])
def test_rbac(client, sessions, role):
    event_id, _ = prepare(sessions)
    with sessions() as db, db.begin():
        db.get(AdminUser, 1).role = role
    for method, path, body in [("GET", ROOT, None), ("GET", f"{ROOT}/{event_id}", None),
            ("POST", f"{ROOT}/{event_id}/approve", None), ("POST", f"{ROOT}/{event_id}/reject", {"reason": "invalid_sale"})]:
        assert client.request(method, path, json=body).status_code == 403


def test_auth_required(client):
    def no_session():
        raise HTTPException(401, "Unauthorized")
    client.app.dependency_overrides[require_admin_user] = no_session
    assert client.get(ROOT).status_code == 401


def test_decision_requires_non_simple_request_header(client, sessions):
    event_id, _ = prepare(sessions)
    client.headers.pop("X-Billing-Review")
    assert client.post(f"{ROOT}/{event_id}/approve").status_code == 422
    assert client.post(f"{ROOT}/{event_id}/reject", json={"reason": "invalid_sale"}).status_code == 422
    with sessions() as db:
        assert db.query(Subscription).count() == 0


@pytest.mark.parametrize("status", ["paid", "refunded", "waiting_payment"])
def test_official_api_persists_only_paid_sale_evidence(sessions, status):
    import httpx
    from dataclasses import replace
    from app.services.kiwify_api import KiwifySalesAPI
    trusted_setup(sessions)
    event_id = receive(sessions)
    responses = iter([
        {"access_token": "synthetic-token", "scope": "sales", "token_type": "Bearer", "expires_in": 86400},
        {"id": ORDER, "product": {"id": PRODUCT}, "status": status, "Customer": {"name": "PRIVATE_MARKER"}},
    ])
    source = KiwifySalesAPI(replace(SETTINGS, client_id="synthetic-client", client_secret="synthetic-secret"),
        reserve=lambda: None, transport=httpx.MockTransport(lambda _: httpx.Response(200, json=next(responses))), clock=lambda: NOW)
    try:
        assert KiwifyVerificationService(sessions, SETTINGS, source=source, clock=lambda: NOW).verify_event(event_id) == V.MANUAL_REVIEW
        with sessions() as db:
            row = db.get(BillingManualReview, event_id)
            assert (row.sale_status == "paid") == (status == "paid")
            assert row.period_start is row.period_end is None
            detail = BillingManualReviewService(db, clock=lambda: NOW).detail(event_id, db.get(AdminUser, 1))
            assert detail["can_approve"] == (status == "paid")
            assert "PRIVATE_MARKER" not in json.dumps(detail, default=str)
    finally:
        source.close()


def test_owner_is_allowed(client, sessions):
    prepare(sessions)
    with sessions() as db, db.begin():
        db.get(AdminUser, 1).role = "owner"
    assert client.get(ROOT).status_code == 200


def test_tenant_isolation_and_context_forgery(client, sessions):
    event_id, _ = prepare(sessions, tenant_id=2)
    assert client.get(ROOT).json() == []
    assert client.get(f"{ROOT}?tenant_id=2").status_code == 403
    for action in ["", "/approve", "/reject"]:
        response = client.get(f"{ROOT}/{event_id}") if not action else client.post(f"{ROOT}/{event_id}{action}", json={"reason": "invalid_sale"})
        assert response.status_code == 404
    with sessions() as db:
        assert db.query(Subscription).count() == 0


def test_approval_without_period_records_binding_but_grants_no_entitlement(client, sessions):
    event_id, _ = prepare(sessions)
    response = client.post(f"{ROOT}/{event_id}/approve")
    assert response.status_code == 200, response.text
    assert response.json()["decision"] == "binding_approved"
    assert response.json()["reason"] == "manual_review_period_missing"
    assert response.json()["access_pending_period"]
    with sessions() as db:
        sub = db.query(Subscription).one()
        assert sub.tenant_id == 1 and sub.provider == "kiwify" and sub.provider_subscription_id == SUB
        assert sub.status == S.INACTIVE and sub.current_period_start is sub.current_period_end is None
        event = db.get(BillingEvent, event_id)
        assert event.subscription_id == sub.id and event.verification_status == V.MANUAL_REVIEW
        assert event.processing_status == P.PENDING
        assert EntitlementService(db).evaluate(1, "orders_monthly", now=NOW).reason == "subscription_inactive"
        assert EntitlementService(db).evaluate(2, "tracking", now=NOW).reason == "legacy_no_subscription"
        audit = db.query(AdminAuditLog).filter_by(action="billing.manual_review_binding_approved").one()
        assert audit.user_id == 1 and audit.actor_type == "user"
        review = db.get(BillingManualReview, event_id)
        assert review.decided_by == 1 and review.decided_at is not None


def test_full_approval_uses_service_and_human_audit(client, sessions):
    event_id, _ = prepare(sessions, period=True)
    response = client.post(f"{ROOT}/{event_id}/approve")
    assert response.status_code == 200, response.text
    assert response.json()["decision"] == "approved"
    with sessions() as db:
        assert db.query(Subscription).one().status == S.ACTIVE
        assert db.get(BillingEvent, event_id).processing_status == P.PROCESSED
        audit = db.query(AdminAuditLog).filter_by(action="subscription.activated").one()
        assert audit.actor_type == "user" and audit.user_id == 1
    assert client.get(ROOT).json() == []


@pytest.mark.parametrize("period", [False, True])
def test_double_approval_is_not_applied_twice(client, sessions, period):
    event_id, _ = prepare(sessions, period=period)
    assert client.post(f"{ROOT}/{event_id}/approve").status_code == 200
    assert client.post(f"{ROOT}/{event_id}/approve").status_code == 409
    with sessions() as db:
        assert db.query(Subscription).count() == 1
        assert db.query(AdminAuditLog).filter(AdminAuditLog.action.like("billing.manual_review%approved")).count() == 1


def test_rejection_retains_event_and_reason(client, sessions):
    event_id, _ = prepare(sessions)
    response = client.post(f"{ROOT}/{event_id}/reject", json={"reason": "incorrect_binding"})
    assert response.status_code == 200
    with sessions() as db:
        assert db.get(BillingEvent, event_id).verification_status == V.REJECTED
        assert db.get(BillingManualReview, event_id).rejection_reason == "incorrect_binding"
        audit = db.query(AdminAuditLog).one()
        assert audit.user_id == 1 and audit.action == "billing.manual_review_rejected"
        assert db.query(Subscription).count() == 0
    assert client.post(f"{ROOT}/{event_id}/approve").status_code == 409
    assert client.post(f"{ROOT}/{event_id}/reject", json={"reason": "invalid_sale"}).status_code == 409


def test_rejection_cannot_store_pii_free_text(client, sessions):
    event_id, _ = prepare(sessions)
    assert client.post(f"{ROOT}/{event_id}/reject", json={"reason": "PRIVATE_MARKER"}).status_code == 422
    assert client.post(f"{ROOT}/{event_id}/reject", json={"reason": "invalid_sale", "email": "PRIVATE_MARKER"}).status_code == 422


def test_processed_event_conflicts(client, sessions):
    event_id, _ = prepare(sessions)
    with sessions() as db, db.begin():
        event = db.get(BillingEvent, event_id)
        event.processing_status, event.processed_at = P.PROCESSED, NOW
    assert client.post(f"{ROOT}/{event_id}/approve").status_code == 409


@pytest.mark.parametrize("missing", ["mapping", "tenant", "paid", "freshness"])
def test_missing_evidence_stays_manual(client, sessions, missing):
    event_id, _ = prepare(sessions)
    with sessions() as db, db.begin():
        if missing == "mapping":
            db.query(BillingOfferMapping).update({"active": False})
        elif missing == "tenant":
            db.query(BillingCheckoutIntent).delete()
            db.get(BillingEvent, event_id).tenant_id = 1  # previously trusted internal link, not a request input
        elif missing == "paid":
            db.get(BillingManualReview, event_id).sale_status = None
        else:
            db.get(BillingManualReview, event_id).sale_checked_at = NOW - timedelta(minutes=6)
    assert client.post(f"{ROOT}/{event_id}/approve").status_code == 422
    with sessions() as db:
        assert db.query(Subscription).count() == 0
        assert db.get(BillingEvent, event_id).verification_status == V.MANUAL_REVIEW


def test_unknown_tenant_not_disclosed(client, sessions):
    event_id, _ = prepare(sessions)
    with sessions() as db, db.begin():
        db.query(BillingCheckoutIntent).delete()
    assert client.get(ROOT).json() == []
    assert client.get(f"{ROOT}/{event_id}").status_code == 404


def test_ambiguous_intents_cannot_approve_or_leak(client, sessions):
    event_id, _ = prepare(sessions)
    from app.services.billing_catalog import BillingCatalogService
    with sessions() as db, db.begin():
        first = db.query(BillingCheckoutIntent).one()
        svc = BillingCatalogService(db)
        intent = svc.create_intent(2, first.plan_id, provider="kiwify", environment="sandbox",
            provider_account_id="account-1", expires_at=NOW + timedelta(hours=1), now=NOW)
        svc.complete_intent(2, intent.public_token, external_subscription_id=SUB, now=NOW)
    assert client.get(ROOT).json() == []
    assert client.post(f"{ROOT}/{event_id}/approve").status_code == 404


def test_audit_failure_rolls_back_entire_decision(client, sessions, monkeypatch):
    event_id, _ = prepare(sessions, period=True)
    def fail(*_, **__):
        raise RuntimeError("PRIVATE_MARKER")
    monkeypatch.setattr("app.services.billing_manual_review.log_admin_action", fail)
    response = client.post(f"{ROOT}/{event_id}/approve")
    assert response.status_code == 503 and "PRIVATE_MARKER" not in response.text
    with sessions() as db:
        assert db.query(Subscription).count() == db.query(AdminAuditLog).count() == 0
        assert db.get(BillingEvent, event_id).verification_status == V.MANUAL_REVIEW
        assert db.get(BillingManualReview, event_id).decision is None


def test_later_trusted_period_activates_same_subscription(sessions):
    event_id, proof = prepare(sessions)
    with sessions() as db:
        svc = BillingManualReviewService(db, clock=lambda: NOW)
        svc.decide(event_id, db.get(AdminUser, 1), approve=True)
        db.commit()
        original = db.query(Subscription).one().id
    from dataclasses import replace
    later = NOW + timedelta(hours=1)
    proof = replace(proof, observed_at=later)
    class CompleteTrustedSource:
        def verify(self, _):
            return VerificationOutcome(V.VERIFIED, "trusted_subscription_confirmed", proof)
    assert KiwifyVerificationService(sessions, SETTINGS, source=CompleteTrustedSource(), clock=lambda: later).verify_event(event_id) == V.VERIFIED
    with sessions() as db:
        sub = db.query(Subscription).one()
        assert sub.id == original and sub.status == S.ACTIVE
        assert db.get(BillingManualReview, event_id).decided_by == 1


def test_incomplete_secondary_recheck_keeps_period_pending(sessions):
    event_id, _ = prepare(sessions)
    with sessions() as db:
        BillingManualReviewService(db, clock=lambda: NOW).decide(event_id, db.get(AdminUser, 1), approve=True)
        db.commit()
    class Incomplete:
        def verify(self, _):
            return VerificationOutcome(V.MANUAL_REVIEW, "sale_confirmed_subscription_unconfirmed")
    assert KiwifyVerificationService(sessions, SETTINGS, source=Incomplete(), clock=lambda: NOW + timedelta(hours=1)).verify_event(event_id) == V.MANUAL_REVIEW
    with sessions() as db:
        assert db.query(Subscription).one().status == S.INACTIVE
        assert db.get(BillingEvent, event_id).verification_error_code == "manual_review_period_missing"


def test_old_sale_is_refreshed_before_human_binding_approval(client, sessions):
    event_id, _ = prepare(sessions)
    with sessions() as db, db.begin():
        db.get(BillingManualReview, event_id).sale_checked_at = NOW - timedelta(hours=2)
    class RefreshSource:
        def verify(self, _):
            return VerificationOutcome(V.MANUAL_REVIEW, "sale_confirmed_subscription_unconfirmed",
                sale=VerifiedSale("account-1", "sandbox", ORDER, PRODUCT, "paid", NOW))
    service = KiwifyVerificationService(sessions, SETTINGS, source=RefreshSource(), clock=lambda: NOW)
    client.app.dependency_overrides[routes.review_verifier] = lambda: service
    response = client.post(f"{ROOT}/{event_id}/approve")
    assert response.status_code == 200 and response.json()["decision"] == "binding_approved"
    with sessions() as db:
        assert db.query(Subscription).one().status == S.INACTIVE


def test_manual_refresh_never_activates_before_human_decision(sessions):
    event_id, proof = prepare(sessions)
    class Complete:
        def verify(self, _):
            return VerificationOutcome(V.VERIFIED, "trusted_subscription_confirmed", proof,
                VerifiedSale("account-1", "sandbox", ORDER, PRODUCT, "paid", NOW))
    service = KiwifyVerificationService(sessions, SETTINGS, source=Complete(), clock=lambda: NOW)
    assert service.verify_event(event_id, manual_refresh=True) == V.MANUAL_REVIEW
    with sessions() as db:
        assert db.query(Subscription).count() == 0
        assert db.get(BillingManualReview, event_id).period_end is not None
        assert db.get(BillingManualReview, event_id).decision is None


def test_retry_after_manual_refresh_preserves_human_gate(sessions):
    event_id, proof = prepare(sessions)
    with sessions() as db, db.begin():
        db.get(BillingEvent, event_id).verification_status = V.RETRYING
    class Complete:
        def verify(self, _):
            return VerificationOutcome(V.VERIFIED, "trusted_subscription_confirmed", proof,
                VerifiedSale("account-1", "sandbox", ORDER, PRODUCT, "paid", NOW))
    assert KiwifyVerificationService(sessions, SETTINGS, source=Complete(), clock=lambda: NOW).verify_event(event_id) == V.MANUAL_REVIEW
    with sessions() as db:
        assert db.query(Subscription).count() == 0


def test_inconclusive_recheck_cannot_reuse_previous_paid_snapshot(sessions):
    event_id, _ = prepare(sessions)
    class NotPaid:
        def verify(self, _):
            return VerificationOutcome(V.MANUAL_REVIEW, "api_sale_not_paid")
    assert KiwifyVerificationService(sessions, SETTINGS, source=NotPaid(), clock=lambda: NOW).verify_event(event_id, manual_refresh=True) == V.MANUAL_REVIEW
    with sessions() as db:
        assert db.get(BillingManualReview, event_id).sale_status is None
        assert not BillingManualReviewService(db, clock=lambda: NOW).detail(event_id, db.get(AdminUser, 1))["can_approve"]


def test_webhook_dates_do_not_become_period_evidence(client, sessions):
    event_id, _ = prepare(sessions)
    with sessions() as db, db.begin():
        event = db.get(BillingEvent, event_id)
        receipt = json.loads(event.raw_payload)
        receipt["projection"].update(approved_date=NOW.isoformat(), start_date=NOW.isoformat(),
                                     next_payment=(NOW + timedelta(days=30)).isoformat())
        event.raw_payload = json.dumps(receipt)
    response = client.post(f"{ROOT}/{event_id}/approve")
    assert response.status_code == 200 and response.json()["decision"] == "binding_approved"
    with sessions() as db:
        sub = db.query(Subscription).one()
        assert sub.current_period_start is sub.current_period_end is None and sub.status == S.INACTIVE


def test_concurrent_approval_once(sessions):
    event_id, _ = prepare(sessions)
    barrier = Barrier(2)
    def approve():
        with sessions() as db:
            actor = db.get(AdminUser, 1)
            barrier.wait()
            try:
                BillingManualReviewService(db, clock=lambda: NOW).decide(event_id, actor, approve=True)
                db.commit()
                return "approved"
            except BillingConflict:
                db.rollback()
                return "conflict"
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: approve(), range(2)))
    assert sorted(results) == ["approved", "conflict"]
    with sessions() as db:
        assert db.query(Subscription).count() == 1
        assert db.query(AdminAuditLog).filter_by(action="billing.manual_review_binding_approved").count() == 1
