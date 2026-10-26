from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.deps import require_admin_user
from app.models.admin_user import AdminUser
from app.models.order import Order
from app.models.plan import Plan
from app.models.plan_entitlement import PlanEntitlement
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.tenant import Tenant
from app.models.whatsapp_config import WhatsAppConfig
from app.routers.admin_delivery_users import router
from app.services.entitlements import EntitlementService
from app.services.plan_seed import seed_plans

NOW = datetime(2026, 10, 6, 12, tzinfo=timezone.utc)
FEATURES = ("orders_monthly", "admin_users", "delivery_users", "tracking", "whatsapp", "inventory",
            "coupons", "loyalty", "custom_domain", "advanced_reports")
EXPECTED = {
    "essential": (300, 1, 1, False, False, False, False, False, False, False),
    "operation": (1500, 3, 5, True, True, True, True, False, False, False),
    "pro": (5000, 10, 15, True, True, True, True, True, True, True),
}


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    @event.listens_for(engine, "connect")
    def enable_fks(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([Tenant(id=1, slug="legacy"), Tenant(id=2, slug="other")])
        seed_plans(session)
        session.commit()
        yield session
    engine.dispose()


def subscribe(db, code="essential", tenant_id=1, **kwargs):
    plan = db.query(Plan).filter_by(code=code).one()
    params = dict(tenant_id=tenant_id, plan_id=plan.id, status=SubscriptionStatus.ACTIVE,
                  current_period_start=NOW - timedelta(days=1), current_period_end=NOW + timedelta(days=20))
    params.update(kwargs)
    sub = Subscription(**params)
    db.add(sub)
    db.commit()
    return sub


def evaluate(db, feature="tracking", tenant_id=1, now=NOW):
    return EntitlementService(db).evaluate(tenant_id, feature, now=now)


def entry(db, code, feature):
    return db.query(PlanEntitlement).join(Plan).filter(Plan.code == code, PlanEntitlement.feature_code == feature).one()


def add_user(db, tenant_id=1, role="admin", active=True, email="user@example.test"):
    db.add(AdminUser(tenant_id=tenant_id, role=role, active=active, email=email, name="User", password_hash="hash"))
    db.commit()


def add_order(db, tenant_id=1, created_at=NOW):
    db.add(Order(tenant_id=tenant_id, cliente_telefone="123", itens="item", created_at=created_at))
    db.commit()


def test_seed_idempotent_and_repairs_partial_catalog_without_overwriting(db):
    ids = [(p.id, p.code) for p in db.query(Plan).all()]
    entitlement_ids = [e.id for e in db.query(PlanEntitlement).all()]
    seed_plans(db)
    db.commit()
    assert [(p.id, p.code) for p in db.query(Plan).all()] == ids
    assert [e.id for e in db.query(PlanEntitlement).all()] == entitlement_ids
    assert db.query(Plan).count() == 3
    assert db.query(PlanEntitlement).count() == 30
    entry(db, "essential", "orders_monthly").limit_value = 999
    db.delete(entry(db, "pro", "loyalty"))
    db.commit()
    seed_plans(db)
    db.commit()
    assert entry(db, "essential", "orders_monthly").limit_value == 999
    assert entry(db, "pro", "loyalty").enabled
    assert db.query(Subscription).count() == 0


@pytest.mark.parametrize("code", EXPECTED)
@pytest.mark.parametrize("feature_index", range(10))
def test_complete_plan_matrix(db, code, feature_index):
    subscribe(db, code)
    feature = FEATURES[feature_index]
    expected = EXPECTED[code][feature_index]
    result = evaluate(db, feature)
    assert result.allowed == (expected if isinstance(expected, bool) else True)
    assert result.limit == (None if isinstance(expected, bool) else expected)
    assert result.usage == (None if isinstance(expected, bool) else 0)
    assert result.reason == ("feature_disabled" if expected is False else "entitled")
    assert result.effective_until == NOW + timedelta(days=20)
    assert entry(db, code, feature).reset_period == ("monthly" if feature == "orders_monthly" else None)


def test_disabled_zero_and_unlimited_are_distinct(db):
    subscribe(db)
    entitlement = entry(db, "essential", "admin_users")
    entitlement.enabled = False
    entitlement.limit_value = 0
    db.commit()
    assert evaluate(db, "admin_users").reason == "feature_disabled"
    entitlement.enabled = True
    db.commit()
    assert evaluate(db, "admin_users").reason == "limit_reached"
    entitlement.limit_value = None
    add_user(db)
    result = evaluate(db, "admin_users")
    assert result.allowed and result.limit is None and result.usage == 1


def test_numeric_capacity_at_boundary_and_user_role_usage(db):
    subscribe(db)
    add_user(db, role="OWNER")
    add_user(db, role="admin", active=False, email="inactive@example.test")
    add_user(db, role="DELIVERY", email="driver@example.test")
    assert evaluate(db, "admin_users").usage == 1
    assert evaluate(db, "admin_users").reason == "limit_reached"
    assert evaluate(db, "delivery_users").usage == 1
    assert evaluate(db, "delivery_users").reason == "limit_reached"


def test_orders_monthly_calendar_boundaries_and_canceled_orders(db):
    subscribe(db)
    start = NOW.replace(day=1, hour=0)
    add_order(db, created_at=start - timedelta(microseconds=1))
    add_order(db, created_at=start)
    add_order(db, created_at=start.replace(month=11))
    order = db.query(Order).filter_by(created_at=start).one()
    order.status = "CANCELED"
    entry(db, "essential", "orders_monthly").limit_value = 1
    db.commit()
    assert evaluate(db, "orders_monthly").usage == 1
    assert evaluate(db, "orders_monthly").reason == "limit_reached"
    assert evaluate(db, "orders_monthly", now=start.replace(month=11)).usage == 1
    assert evaluate(db, "orders_monthly", now=start.replace(month=12)).usage == 0


def test_tenant_without_subscription_is_legacy_and_read_only(db):
    tenant = db.get(Tenant, 1)
    before = {column.name: getattr(tenant, column.name) for column in Tenant.__table__.columns}
    for feature in FEATURES:
        result = evaluate(db, feature)
        assert result.allowed and result.limit is None
        assert result.reason == "legacy_no_subscription"
    assert db.query(Subscription).count() == 0
    assert {column.name: getattr(tenant, column.name) for column in Tenant.__table__.columns} == before
    assert not db.new and not db.dirty
    assert evaluate(db, tenant_id=999).reason == "tenant_not_found"
    assert evaluate(db, "not_a_feature").reason == "unknown_feature"


@pytest.mark.parametrize("status", [SubscriptionStatus.INACTIVE, SubscriptionStatus.CANCELED, SubscriptionStatus.EXPIRED])
def test_non_entitling_subscription_status(db, status):
    subscribe(db, "pro", status=status)
    result = evaluate(db)
    assert not result.allowed and result.reason == f"subscription_{status.value}"


def test_active_period_expiration_does_not_mutate_status(db):
    sub = subscribe(db, "pro", current_period_end=NOW)
    assert evaluate(db).reason == "subscription_expired"
    assert sub.status == SubscriptionStatus.ACTIVE
    assert evaluate(db, now=NOW - timedelta(microseconds=1)).allowed
    sub.current_period_end = None
    db.commit()
    assert evaluate(db).allowed and evaluate(db).effective_until is None


def test_trial_period_and_naive_utc_datetime(db):
    subscribe(db, "pro", status=SubscriptionStatus.TRIALING, trial_end=NOW.replace(tzinfo=None))
    assert evaluate(db).reason == "subscription_expired"
    assert evaluate(db, now=NOW - timedelta(seconds=1)).allowed


@pytest.mark.parametrize("grace, allowed", [(None, False), (NOW, False), (NOW + timedelta(days=1), True)])
def test_past_due_grace(db, grace, allowed):
    subscribe(db, "pro", status=SubscriptionStatus.PAST_DUE, current_period_end=NOW - timedelta(days=1), grace_until=grace)
    assert evaluate(db).allowed == allowed
    assert evaluate(db).effective_until == grace


def test_scheduled_cancel_keeps_access_until_period_end(db):
    subscribe(db, "pro", cancel_at_period_end=True, canceled_at=NOW)
    assert evaluate(db).allowed
    assert evaluate(db, now=NOW + timedelta(days=20)).reason == "subscription_expired"


def test_future_subscription_inactive_plan_and_missing_entitlement(db):
    sub = subscribe(db, "pro", current_period_start=NOW + timedelta(days=1))
    assert evaluate(db).reason == "subscription_not_started"
    sub.current_period_start = NOW
    plan = db.get(Plan, sub.plan_id)
    plan.active = False
    db.commit()
    assert evaluate(db).reason == "plan_inactive"
    plan.active = True
    db.delete(entry(db, "pro", "tracking"))
    db.commit()
    assert evaluate(db).reason == "entitlement_missing"


def test_tenant_isolation_of_subscription_and_usage(db):
    subscribe(db, "essential", tenant_id=1)
    subscribe(db, "pro", tenant_id=2)
    add_user(db, tenant_id=2)
    add_order(db, tenant_id=2)
    assert not evaluate(db, "tracking", tenant_id=1).allowed
    assert evaluate(db, "tracking", tenant_id=2).allowed
    assert evaluate(db, "admin_users", tenant_id=1).usage == 0
    assert evaluate(db, "admin_users", tenant_id=2).usage == 1
    assert evaluate(db, "orders_monthly", tenant_id=1).usage == 0
    assert evaluate(db, "orders_monthly", tenant_id=2).usage == 1
    db.get(Tenant, 1).slug = "renamed"
    db.commit()
    assert not evaluate(db, "tracking").allowed


def test_entitlement_does_not_enable_whatsapp_config(db):
    subscribe(db, "pro")
    config = WhatsAppConfig(tenant_id=1, is_enabled=False)
    db.add(config)
    db.commit()
    assert evaluate(db, "whatsapp").allowed
    assert not config.is_enabled


@pytest.mark.parametrize("commercial_subscription", [False, True])
def test_existing_delivery_operation_remains_unblocked(db, monkeypatch, commercial_subscription):
    if commercial_subscription:
        subscribe(db, "essential", status=SubscriptionStatus.EXPIRED)
        assert not evaluate(db, "delivery_users").allowed
    monkeypatch.setattr("app.routers.admin_delivery_users.log_admin_action", lambda *args, **kwargs: None)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[require_admin_user] = lambda: SimpleNamespace(id=10, tenant_id=1, role="admin")
    client = TestClient(app)
    # Two active delivery users exceed Essential's limit of one; still no enforcement.
    for index in range(2):
        response = client.post("/api/admin/1/delivery-users", json={"name": "Driver", "email": f"driver{index}@example.com", "password": "secret123"})
        assert response.status_code == 201
    assert evaluate(db, "delivery_users").usage == 2


@pytest.mark.parametrize("sql", [
    "INSERT INTO plans (code, name) VALUES ('essential', 'Duplicate')",
    "INSERT INTO plan_entitlements (plan_id, feature_code) SELECT id, 'tracking' FROM plans WHERE code='essential'",
    "INSERT INTO plan_entitlements (plan_id, feature_code, limit_value) SELECT id, 'invalid', -1 FROM plans WHERE code='essential'",
    "INSERT INTO plan_entitlements (plan_id, feature_code, reset_period) SELECT id, 'invalid', 'daily' FROM plans WHERE code='essential'",
    "INSERT INTO subscriptions (tenant_id, plan_id) SELECT 999, id FROM plans WHERE code='essential'",
    "INSERT INTO subscriptions (tenant_id, plan_id) VALUES (1, 999)",
    "INSERT INTO subscriptions (tenant_id, plan_id, status) SELECT 1, id, 'paid' FROM plans WHERE code='essential'",
])
def test_domain_constraints(db, sql):
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(text(sql))


def test_only_one_current_subscription_per_tenant(db):
    subscribe(db)
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(Subscription(tenant_id=1, plan_id=db.query(Plan.id).first()[0]))
        db.flush()



def test_observation_never_autoflushes_pending_operational_changes(db):
    tenant = db.get(Tenant, 1)
    tenant.business_name = "Pending edit"
    assert evaluate(db).allowed
    assert tenant in db.dirty
    with db.no_autoflush:
        assert db.execute(text("SELECT business_name FROM tenants WHERE id=1")).scalar_one() == "Loja Padrão"


def test_unsupported_reset_and_unavailable_boolean_usage_are_explicit(db):
    subscribe(db, "pro")
    entitlement = entry(db, "pro", "admin_users")
    entitlement.reset_period = "monthly"
    db.commit()
    assert evaluate(db, "admin_users").reason == "unsupported_reset_period"
    entry(db, "pro", "tracking").limit_value = 1
    db.commit()
    assert evaluate(db).reason == "usage_unavailable"
