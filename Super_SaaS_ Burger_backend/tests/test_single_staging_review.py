import json

import httpx
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
import app.models
from app.models.tenant import Tenant
from app.models.admin_user import AdminUser
from app.models.plan import Plan
from app.models.billing_event import BillingEvent
from app.models.billing_manual_review import BillingManualReview
from app.models.billing_offer_mapping import BillingOfferMapping
from app.models.billing_checkout_intent import BillingCheckoutIntent
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.admin_audit_log import AdminAuditLog
from app.services.plan_seed import seed_plans
from app.services.entitlements import EntitlementService
from app.services.billing_manual_review import (
    BillingManualReviewService,
    ReviewNotFound,
)
from app.services.billing_common import BillingError
from scripts.prepare_single_staging_review import prepare_single


@pytest.fixture
def staging(monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError("Real HTTP forbidden")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", no_network)
    engine = sa.create_engine("sqlite://")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db, db.begin():
        seed_plans(db)
        t = Tenant(slug="meuburger", name="SYNTHETIC")
        other = Tenant(slug="other", name="SYNTHETIC OTHER")
        db.add_all([t, other])
        db.flush()
        tid = t.id
        for tenant, role in ((t, "owner"), (t, "operator"), (other, "owner")):
            db.add(
                AdminUser(
                    tenant_id=tenant.id,
                    email=f"{role}@example.com",
                    name="SYNTHETIC",
                    role=role,
                    password_hash="unused-synthetic-hash",
                )
            )
    yield sessions, tid
    engine.dispose()


@pytest.mark.parametrize("approve", [True, False])
def test_one_event_idempotent_isolated_no_access_and_decision_preserved(
    staging, approve
):
    sessions, tid = staging
    first = prepare_single(sessions, tid)
    second = prepare_single(sessions, tid)
    assert first == second and first["real_provider_calls"] is False
    eid = first["billing_event_id"]
    with sessions() as db, db.begin():
        assert db.query(Tenant).count() == 2  # no new tenants/users
        assert db.query(AdminUser).count() == 3
        assert (
            db.query(BillingEvent).count() == db.query(BillingManualReview).count() == 1
        )
        assert (
            db.query(BillingOfferMapping).count()
            == db.query(BillingCheckoutIntent).count()
            == 1
        )
        assert db.query(Subscription).count() == 1
        owner = db.query(AdminUser).filter_by(tenant_id=tid, role="owner").one()
        operator = db.query(AdminUser).filter_by(tenant_id=tid, role="operator").one()
        other = db.query(AdminUser).filter(AdminUser.tenant_id != tid).one()
        svc = BillingManualReviewService(db)
        assert len(svc.list(owner)) == 1
        assert svc.list(other) == []
        with pytest.raises(ReviewNotFound):
            svc.detail(eid, other)
        with pytest.raises(BillingError):
            svc.list(operator)
        assert svc.detail(eid, owner)["can_approve"]
        projection = json.loads(db.get(BillingEvent, eid).raw_payload)["projection"]
        assert not {"email", "phone", "document", "Customer"} & projection.keys()
        result = svc.decide(
            eid,
            owner,
            approve=approve,
            rejection_reason=None if approve else "invalid_sale",
        )
        assert result["decision"] == ("binding_approved" if approve else "rejected")
        with pytest.raises(BillingError):
            svc.decide(eid, owner, approve=approve, rejection_reason="invalid_sale")
        sub = db.query(Subscription).one()
        assert sub.status == SubscriptionStatus.INACTIVE
        assert sub.current_period_start is None and sub.current_period_end is None
        assert not EntitlementService(db).evaluate(tid, "orders_monthly").allowed
        if approve:
            assert result["reason"] == "manual_review_period_missing"
        action = (
            "billing.manual_review_binding_approved"
            if approve
            else "billing.manual_review_rejected"
        )
        assert (
            db.query(AdminAuditLog)
            .filter_by(
                action=action, tenant_id=tid, actor_type="user", user_id=owner.id
            )
            .count()
            == 1
        )
    rerun = prepare_single(sessions, tid)
    assert rerun["decision"] == result["decision"]
    with sessions() as db:
        assert db.query(BillingEvent).count() == 1


def test_wrong_tenant_fails_without_writes(staging):
    sessions, tid = staging
    with pytest.raises(ValueError, match="tenant_mismatch"):
        prepare_single(sessions, tid + 1)
    with sessions() as db:
        assert db.query(BillingEvent).count() == db.query(Subscription).count() == 0
        assert db.query(BillingOfferMapping).count() == 0


def test_existing_commercial_subscription_is_not_modified(staging):
    sessions, tid = staging
    with sessions() as db, db.begin():
        plan = db.query(Plan).filter_by(code="pro").one()
        db.add(
            Subscription(
                tenant_id=tid, plan_id=plan.id, status=SubscriptionStatus.ACTIVE
            )
        )
    with pytest.raises(ValueError, match="must_not_be_modified"):
        prepare_single(sessions, tid)
    with sessions() as db:
        assert db.query(Subscription).one().status == SubscriptionStatus.ACTIVE
        assert (
            db.query(BillingEvent).count() == db.query(BillingOfferMapping).count() == 0
        )
