from argparse import Namespace
import secrets

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
import app.models
from app.models.admin_audit_log import AdminAuditLog
from app.models.admin_user import AdminUser
from app.models.billing_event import BillingEvent
from app.models.billing_manual_review import BillingManualReview
from app.models.subscription import Subscription, SubscriptionStatus
from app.services.billing_manual_review import (
    BillingManualReviewService,
    ReviewNotFound,
)
from app.services.entitlements import EntitlementService
from scripts.prepare_railway_staging import prepare, validate_target


def target():
    args = Namespace(
        confirm_staging=True,
        expected_db_host="synthetic-db.railway.internal",
        expected_database="synthetic_stage",
        batch="initial",
    )
    env = {
        "ENV": "staging",
        "ENVIRONMENT": "staging",
        "DATABASE_URL": "postgresql+psycopg://synthetic-db.railway.internal/synthetic_stage",
        "KIWIFY_UNTRUSTED_INGRESS_ENABLED": "false",
        "FEATURE_LEGACY_ADMIN": "false",
        "DEV_BOOTSTRAP_ALLOW": "false",
    }
    return args, env


@pytest.mark.parametrize(
    "override",
    [
        {"ENV": "production"},
        {"ENVIRONMENT": "production"},
        {"KIWIFY_UNTRUSTED_INGRESS_ENABLED": "true"},
        {"FEATURE_LEGACY_ADMIN": "true"},
        {"DEV_BOOTSTRAP_ALLOW": "true"},
        {"KIWIFY_API_CLIENT_ID": "synthetic-marker"},
        {"DATABASE_URL": "sqlite://"},
        {"DATABASE_URL": "postgresql+psycopg://other/synthetic_stage"},
    ],
)
def test_target_rejects_unsafe_or_mismatched_environment(override):
    args, env = target()
    env.update(override)
    with pytest.raises(ValueError):
        validate_target(args, env)


def test_target_requires_explicit_confirmation_and_accepts_safe_target():
    args, env = target()
    assert validate_target(args, env).database == "synthetic_stage"
    args.confirm_staging = False
    with pytest.raises(ValueError):
        validate_target(args, env)


def test_synthetic_seed_idempotence_and_human_decisions_without_period(monkeypatch):
    # Every provider call MUST have an injected MockTransport; no network needed.
    import httpx

    def forbid_real_http(*args, **kwargs):
        raise AssertionError("Real provider HTTP is forbidden")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbid_real_http)
    engine = sa.create_engine("sqlite://")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    password = secrets.token_urlsafe(24)
    try:
        first = prepare(sessions, password, "initial")
        second = prepare(sessions, password, "initial")
        assert first == second and first["real_provider_calls"] is False
        a = first["tenant_ids"]["a"]
        with sessions() as db, db.begin():
            assert db.query(BillingEvent).count() == 4
            assert db.query(Subscription).count() == 2
            owner = db.query(AdminUser).filter_by(tenant_id=a, role="owner").one()
            other_id = next(r["id"] for r in first["reviews"] if r["tenant"] == "b")
            with pytest.raises(ReviewNotFound):
                BillingManualReviewService(db).detail(other_id, owner)
            approve_id = next(
                r["id"]
                for r in first["reviews"]
                if r["tenant"] == "a" and r["scenario"] == "approve"
            )
            reject_id = next(
                r["id"]
                for r in first["reviews"]
                if r["tenant"] == "a" and r["scenario"] == "reject"
            )
            approved = BillingManualReviewService(db).decide(
                approve_id, owner, approve=True
            )
            assert approved["decision"] == "binding_approved"
            BillingManualReviewService(db).decide(
                reject_id, owner, approve=False, rejection_reason="invalid_sale"
            )
            assert (
                db.query(AdminAuditLog)
                .filter_by(
                    action="billing.manual_review_binding_approved",
                    tenant_id=a,
                    user_id=owner.id,
                )
                .count()
                == 1
            )
            sub = db.query(Subscription).filter_by(tenant_id=a).one()
            assert (
                sub.status == SubscriptionStatus.INACTIVE
                and sub.current_period_end is None
            )
            assert not EntitlementService(db).evaluate(a, "orders_monthly").allowed
            assert (
                db.get(BillingEvent, approve_id).verification_error_code
                == "manual_review_period_missing"
            )
        prepare(sessions, password, "initial")
        with sessions() as db:
            assert (
                db.get(BillingManualReview, approve_id).decision == "binding_approved"
            )
            assert db.get(BillingManualReview, reject_id).decision == "rejected"
    finally:
        engine.dispose()
