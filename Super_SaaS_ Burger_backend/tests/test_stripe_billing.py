"""Payment guardrails: no activation at checkout, verified webhook only."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from test_billing_phase2 import database
from app.core.database import get_db
from app.core.stripe_config import StripeOffer, StripeSettings
from app.models.admin_user import AdminUser
from app.models.plan import Plan
from app.models.subscription import Subscription, SubscriptionStatus
from app.routers import stripe_billing as routes
from app.services.billing_common import BillingError
from app.services.stripe_billing import StripeBilling
from app.services.subscriptions import SubscriptionService

SETTINGS = StripeSettings(True, "sandbox", "acct_test123", "pk_test_123", "sk_test_123",
    "whsec_synthetic_secret_123456", (StripeOffer("essential", "price_test123", 9990),))


def test_restricted_live_key_is_accepted_but_test_key_is_not():
    live = replace(SETTINGS, environment="production", publishable_key="pk_live_123", secret_key="rk_live_123")
    live.validate()
    with pytest.raises(BillingError, match="incomplete_stripe_configuration"):
        replace(live, secret_key="rk_test_123").validate()


@pytest.fixture
def db():
    engine = database(create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool))
    with Session(engine) as session:
        plan = session.query(Plan).filter_by(code="essential").one()
        SubscriptionService(session).create_subscription(1, plan.id, provider="stripe")
        session.commit()
        yield session
    engine.dispose()


def remote(status="incomplete"):
    start = int((datetime.now(timezone.utc) - timedelta(minutes=1)).timestamp())
    return {"id": "sub_test123", "customer": "cus_test123", "status": status,
        "cancel_at_period_end": False,
        "latest_invoice": {"confirmation_secret": {"client_secret": "pi_test_secret_123"}},
        "items": {"data": [{"price": {"id": "price_test123"},
            "current_period_start": start, "current_period_end": start + 30 * 86400}]}}


def test_checkout_keeps_subscription_inactive_and_reuses_stripe_contract(db, monkeypatch):
    calls = []
    def fake(settings, method, path, **kwargs):
        calls.append((method, path))
        if path.startswith("prices/"):
            return {"active": True, "currency": "brl", "unit_amount": 9990,
                "recurring": {"interval": "month", "interval_count": 1}}
        if path == "customers":
            return {"id": "cus_test123"}
        return remote()
    monkeypatch.setattr("app.services.stripe_billing.stripe_request", fake)
    user = db.get(AdminUser, 1)
    result = StripeBilling(db, SETTINGS).checkout(user, "essential")
    assert result["client_secret"] == "pi_test_secret_123"
    assert db.query(Subscription).filter_by(tenant_id=1).one().status == SubscriptionStatus.INACTIVE
    assert StripeBilling(db, SETTINGS).checkout(user, "essential")["client_secret"] == result["client_secret"]
    assert calls.count(("POST", "subscriptions")) == 1


def test_checkout_rejects_price_mismatch_before_creating_customer(db, monkeypatch):
    calls = []
    def fake(settings, method, path, **kwargs):
        calls.append(path)
        return {"active": True, "currency": "brl", "unit_amount": 10,
            "recurring": {"interval": "month", "interval_count": 1}}
    monkeypatch.setattr("app.services.stripe_billing.stripe_request", fake)
    with pytest.raises(BillingError):
        StripeBilling(db, SETTINGS).checkout(db.get(AdminUser, 1), "essential")
    assert calls == ["prices/price_test123"]


def test_webhook_requires_signature_and_activates_once(db, monkeypatch):
    sub = db.query(Subscription).filter_by(tenant_id=1).one()
    sub.provider_customer_id, sub.provider_subscription_id = "cus_test123", "sub_test123"
    db.commit()
    monkeypatch.setattr(routes, "stripe_settings", lambda: SETTINGS)
    monkeypatch.setattr(routes, "stripe_request", lambda *a, **k: remote("active"))
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_db] = lambda: db
    event = {"id": "evt_test123", "type": "customer.subscription.updated", "livemode": False,
        "created": int(time.time()), "data": {"object": {"id": "sub_test123"}}}
    body = json.dumps(event).encode()
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.post("/api/webhooks/billing/stripe", content=body).status_code == 401
        assert db.query(Subscription).filter_by(tenant_id=1).one().status == SubscriptionStatus.INACTIVE
        signed = str(int(time.time()))
        digest = hmac.new(SETTINGS.webhook_secret.encode(), signed.encode() + b"." + body, hashlib.sha256).hexdigest()
        headers = {"Stripe-Signature": f"t={signed},v1={digest}"}
        response = client.post("/api/webhooks/billing/stripe", content=body, headers=headers)
        assert response.status_code == 200, response.text
        assert db.query(Subscription).filter_by(tenant_id=1).one().status == SubscriptionStatus.ACTIVE
        assert client.post("/api/webhooks/billing/stripe", content=body, headers=headers).json()["duplicate"]
