from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from threading import Barrier
import time
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.deps import require_admin_user
from app.models.admin_audit_log import AdminAuditLog
from app.models.admin_user import AdminUser
from app.models.billing_checkout_intent import BillingCheckoutIntent, BillingIntentStatus
from app.models.billing_event import BillingEvent, BillingEventStatus
from app.models.billing_offer_mapping import BillingOfferMapping
from app.models.plan import Plan
from app.models.subscription import Subscription, SubscriptionStatus as Status
from app.models.tenant import Tenant
from app.routers.admin_audit import router as audit_router
from app.services.admin_audit import log_admin_action
from app.services.billing_catalog import BillingCatalogService
from app.services.billing_common import BillingConflict, BillingError
from app.services.billing_inbox import BillingInboxService
from app.services.entitlements import EntitlementService
from app.services.plan_seed import seed_plans
from app.services.subscriptions import SubscriptionActor, SubscriptionService

NOW = datetime(2026, 10, 6, 12, tzinfo=timezone.utc)
END = NOW + timedelta(days=30)
# Independent expected policy: do not derive assertions from the service's map.
EXPECTED_TRANSITIONS = {
    Status.INACTIVE: {Status.TRIALING, Status.ACTIVE, Status.CANCELED},
    Status.TRIALING: {Status.ACTIVE, Status.CANCELED, Status.EXPIRED},
    Status.ACTIVE: {Status.PAST_DUE, Status.CANCELED, Status.EXPIRED},
    Status.PAST_DUE: {Status.ACTIVE, Status.CANCELED, Status.EXPIRED},
    Status.CANCELED: {Status.EXPIRED},
    Status.EXPIRED: set(),
}


def database(engine):
    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    with Session(engine) as db, db.begin():
        db.add_all([Tenant(id=1, slug="legacy"), Tenant(id=2, slug="other")])
        db.flush()
        db.add_all([AdminUser(id=1, tenant_id=1, email="one@example.test", name="One", password_hash="hash"),
                    AdminUser(id=2, tenant_id=2, email="two@example.test", name="Two", password_hash="hash")])
        seed_plans(db)
    return engine


@pytest.fixture
def db():
    engine = database(create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool))
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture
def file_engine(tmp_path):
    engine = database(create_engine(f"sqlite:///{tmp_path / 'concurrent.db'}", connect_args={"timeout": 10, "check_same_thread": False}))
    yield engine
    engine.dispose()


def plan_id(db, code="essential"):
    return db.query(Plan.id).filter_by(code=code).scalar()


def service(db, now=NOW):
    return SubscriptionService(db, clock=lambda: now)


def make_subscription(db, status=Status.INACTIVE, tenant_id=1, provider=None):
    sub = service(db).create_subscription(tenant_id, plan_id(db), provider=provider)
    if status == Status.TRIALING:
        service(db).start_trial(tenant_id, sub.id, trial_end=END)
    elif status in {Status.ACTIVE, Status.PAST_DUE, Status.CANCELED, Status.EXPIRED}:
        service(db).activate_subscription(tenant_id, sub.id, current_period_end=END)
        if status == Status.PAST_DUE:
            service(db).mark_past_due(tenant_id, sub.id, grace_until=END)
        elif status == Status.CANCELED:
            service(db).cancel_subscription(tenant_id, sub.id)
        elif status == Status.EXPIRED:
            service(db, END).expire_subscription(tenant_id, sub.id)
    db.commit()
    return sub


def mapping_args(db, **changes):
    params = dict(provider="kiwify", environment="sandbox", provider_account_id="account-1",
                  external_product_id="product-1", external_offer_id="offer-1", plan_id=plan_id(db))
    params.update(changes)
    return params


def intent(db, tenant_id=1, **changes):
    params = dict(provider="kiwify", environment="sandbox", provider_account_id="account-1", expires_at=END, now=NOW)
    params.update(changes)
    return BillingCatalogService(db).create_intent(tenant_id, plan_id(db), **params)


def receipt(db, **changes):
    params = dict(provider="kiwify", environment="sandbox", provider_account_id="account-1",
                  provider_event_id="event-1", event_type="subscription_paid", payload={"test": True})
    params.update(changes)
    return BillingInboxService(db).receive_event(**params)


def test_mapping_explicit_unique_and_scope_separation(db):
    catalog = BillingCatalogService(db)
    first = catalog.create_mapping(**mapping_args(db))
    assert first.plan_id == plan_id(db)
    with pytest.raises(BillingConflict, match="offer_mapping_conflict"):
        catalog.create_mapping(**mapping_args(db))
    for changes in ({"environment": "production"}, {"provider_account_id": "account-2"},
                    {"provider": "future_provider"}, {"external_product_id": "product-2"}, {"external_offer_id": "offer-2"}):
        catalog.create_mapping(**mapping_args(db, **changes))
    assert db.query(BillingOfferMapping).count() == 6
    key = mapping_args(db)
    key.pop("plan_id")
    assert catalog.resolve_mapping(**key).id == first.id
    first.active = False
    db.flush()
    with pytest.raises(BillingError, match="offer_not_mapped"):
        catalog.resolve_mapping(**key)


@pytest.mark.parametrize("changes", [{"provider_account_id": ""}, {"external_offer_id": ""},
                                      {"environment": "unknown"}, {"plan_id": 999}])
def test_mapping_rejects_ambiguous_or_missing_identity(db, changes):
    with pytest.raises(BillingError):
        BillingCatalogService(db).create_mapping(**mapping_args(db, **changes))


def test_intent_tokens_opaque_and_tenant_bound(db):
    intents = [intent(db) for _ in range(12)]
    tokens = [entry.public_token for entry in intents]
    assert len(set(tokens)) == len(tokens)
    assert all(re.fullmatch(r"[A-Za-z0-9_-]{43}", token) for token in tokens)
    assert all(not token.isdigit() for token in tokens)
    with pytest.raises(BillingError, match="intent_not_found"):
        BillingCatalogService(db).get_pending_intent(2, tokens[0], now=NOW)
    assert BillingCatalogService(db).get_pending_intent(1, tokens[0], now=NOW).id == intents[0].id
    assert db.query(Subscription).count() == 0


def test_expired_intent_cannot_complete_or_link(db):
    entry = intent(db)
    event = receipt(db).event
    catalog = BillingCatalogService(db)
    with pytest.raises(BillingError, match="intent_expired"):
        catalog.complete_intent(1, entry.public_token, now=END)
    with pytest.raises(BillingError, match="intent_expired_or_canceled"):
        BillingInboxService(db).link_event(event.id, 1, checkout_intent_id=entry.id, now=END)
    catalog.expire_intent(1, entry.id, now=END)
    assert entry.status == BillingIntentStatus.EXPIRED
    assert entry.completed_at is None
    with pytest.raises(BillingError, match="intent_expiration_not_future"):
        intent(db, expires_at=NOW)


def test_intent_completes_once_and_binds_external_ids(db):
    entry = intent(db)
    completed = BillingCatalogService(db).complete_intent(1, entry.public_token, external_checkout_id="checkout-1",
        external_customer_id="customer-1", external_subscription_id="subscription-1", now=NOW)
    assert completed.status == BillingIntentStatus.COMPLETED
    assert completed.external_checkout_id == "checkout-1"
    assert completed.external_subscription_id == "subscription-1"
    with pytest.raises(BillingError, match="intent_not_pending"):
        BillingCatalogService(db).complete_intent(1, entry.public_token, now=NOW)


def test_event_deduplication_hash_redaction_and_scope(db, caplog):
    payload = {"email": "sensitive@example.test", "name": "Personal Name", "secret": "never-persist-this", "nested": {"token": "private-token"}}
    first = receipt(db, payload=payload)
    second = receipt(db, payload=dict(reversed(list(payload.items()))))
    assert first.created and not second.created and first.event.id == second.event.id
    assert first.event.payload_hash == hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    stored = first.event.raw_payload
    assert json.loads(stored)["redacted"] is True
    for value in ("sensitive@example.test", "Personal Name", "never-persist-this", "private-token"):
        assert value not in stored and value not in caplog.text
    for changes in ({"environment": "production"}, {"provider_account_id": "account-2"}, {"provider": "other"}):
        assert receipt(db, **changes).created
    assert db.query(BillingEvent).count() == 4
    assert first.event.processing_status == BillingEventStatus.PENDING
    assert first.event.attempt_count == 0


def test_duplicate_event_with_changed_payload_or_metadata_is_rejected(db):
    original = receipt(db).event
    for changes in ({"payload": {"different": True}}, {"schema_version": 2}, {"event_type": "other"}, {"occurred_at": NOW}):
        with pytest.raises(BillingConflict, match="event_identity_payload_mismatch"):
            receipt(db, **changes)
    assert db.query(BillingEvent).count() == 1
    assert original.event_type == "subscription_paid"


def test_event_database_constraints_do_not_depend_on_receive_service(db):
    receipt(db)
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(text("INSERT INTO billing_events (provider, environment, provider_account_id, provider_event_id, event_type, payload_hash, raw_payload) VALUES ('kiwify', 'sandbox', 'account-1', 'event-1', 'paid', :hash, '{}')"), {"hash": "a" * 64})


def test_concurrent_event_receipts_create_one_durable_row(file_engine):
    barrier = Barrier(2)
    def worker():
        with Session(file_engine) as db:
            barrier.wait(timeout=5)
            result = receipt(db)
            return result.event.id, result.created
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: worker(), range(2)))
    assert len({event_id for event_id, _ in results}) == 1
    assert sorted(created for _, created in results) == [False, True]
    with Session(file_engine) as db:
        assert db.query(BillingEvent).count() == 1


def test_subscription_creation_and_automatic_audit(db):
    sub = make_subscription(db)
    assert sub.status == Status.INACTIVE and sub.version == 1
    log = db.query(AdminAuditLog).one()
    assert log.action == "subscription.created" and log.tenant_id == 1
    assert log.user_id is None and log.actor_type == "system"
    meta = json.loads(log.meta_json)
    assert meta["before"] is None
    assert meta["after"]["status"] == "inactive"
    assert meta["subscription_id"] == sub.id
    assert meta["origin"] == "internal"


@pytest.mark.parametrize("provider", [None, "kiwify", "future_provider"])
def test_lifecycle_is_provider_independent(db, provider):
    sub = make_subscription(db, provider=provider)
    svc = service(db)
    svc.start_trial(1, sub.id, trial_end=END)
    assert sub.status == Status.TRIALING
    svc.activate_subscription(1, sub.id, current_period_end=END)
    svc.mark_past_due(1, sub.id, grace_until=END)
    assert sub.status == Status.PAST_DUE and sub.past_due_since is not None
    svc.activate_subscription(1, sub.id, current_period_end=END)
    assert sub.status == Status.ACTIVE and sub.grace_until is None and sub.past_due_since is None
    svc.schedule_cancellation(1, sub.id)
    assert sub.status == Status.ACTIVE and sub.cancel_at_period_end
    assert EntitlementService(db).evaluate(1, "orders_monthly", now=NOW).allowed
    svc.change_plan(1, sub.id, plan_id(db, "pro"))
    assert sub.plan_id == plan_id(db, "pro")
    svc.cancel_subscription(1, sub.id)
    assert sub.status == Status.CANCELED and sub.canceled_at is not None and not sub.cancel_at_period_end
    svc.expire_subscription(1, sub.id)
    assert sub.status == Status.EXPIRED
    actions = [row.action for row in db.query(AdminAuditLog).order_by(AdminAuditLog.id)]
    assert actions == ["subscription.created", "subscription.trial_started", "subscription.activated", "subscription.past_due",
                       "subscription.activated", "subscription.cancellation_scheduled", "subscription.plan_changed",
                       "subscription.canceled", "subscription.expired"]
    logs = list(db.query(AdminAuditLog).order_by(AdminAuditLog.id))
    for previous, current in zip(logs, logs[1:]):
        assert json.loads(previous.meta_json)["after"] == json.loads(current.meta_json)["before"]
    changed = json.loads(logs[6].meta_json)
    assert changed["previous_plan_id"] == plan_id(db) and changed["new_plan_id"] == plan_id(db, "pro")


@pytest.mark.parametrize("status", list(Status))
@pytest.mark.parametrize("target", [Status.TRIALING, Status.ACTIVE, Status.PAST_DUE, Status.CANCELED, Status.EXPIRED])
def test_transition_matrix(db, status, target):
    sub = make_subscription(db, status)
    svc = service(db, END)
    calls = {
        Status.TRIALING: lambda: svc.start_trial(1, sub.id, trial_end=END + timedelta(days=10)),
        Status.ACTIVE: lambda: svc.activate_subscription(1, sub.id, current_period_end=END + timedelta(days=10)),
        Status.PAST_DUE: lambda: svc.mark_past_due(1, sub.id),
        Status.CANCELED: lambda: svc.cancel_subscription(1, sub.id),
        Status.EXPIRED: lambda: svc.expire_subscription(1, sub.id),
    }
    before_count = db.query(AdminAuditLog).count()
    if target in EXPECTED_TRANSITIONS[status]:
        calls[target]()
        assert sub.status == target
        assert db.query(AdminAuditLog).count() == before_count + 1
    else:
        with pytest.raises(BillingError):
            calls[target]()
        assert sub.status == status
        assert db.query(AdminAuditLog).count() == before_count


def test_active_expiration_requires_effective_period_end(db):
    sub = make_subscription(db, Status.ACTIVE)
    with pytest.raises(BillingError, match="subscription_not_due_for_expiration"):
        service(db).expire_subscription(1, sub.id)
    assert sub.status == Status.ACTIVE
    service(db, END).expire_subscription(1, sub.id)
    assert sub.status == Status.EXPIRED


def test_past_due_cannot_expire_inside_grace_and_can_reactivate(db):
    sub = make_subscription(db, Status.PAST_DUE)
    with pytest.raises(BillingError, match="subscription_not_due_for_expiration"):
        service(db).expire_subscription(1, sub.id)
    service(db).activate_subscription(1, sub.id, current_period_end=END)
    assert sub.status == Status.ACTIVE and sub.grace_until is None


def test_invalid_period_reverts_status_and_creates_no_audit(db):
    sub = make_subscription(db)
    count = db.query(AdminAuditLog).count()
    with pytest.raises(BillingError, match="invalid_active_period"):
        service(db).activate_subscription(1, sub.id, current_period_end=NOW)
    assert sub.status == Status.INACTIVE
    assert db.query(AdminAuditLog).count() == count


def test_subscription_tenant_isolation_and_user_actor(db):
    sub = make_subscription(db)
    for actor in (SubscriptionActor(actor_type="user", user_id=2), SubscriptionActor(actor_type="provider", user_id=1)):
        with pytest.raises(BillingError):
            service(db).activate_subscription(1, sub.id, current_period_end=END, actor=actor)
    with pytest.raises(BillingError, match="subscription_not_found"):
        service(db).activate_subscription(2, sub.id, current_period_end=END)
    actor = SubscriptionActor(actor_type="user", user_id=1, origin="admin", correlation_id="correlation-1")
    service(db).activate_subscription(1, sub.id, current_period_end=END, actor=actor)
    log = db.query(AdminAuditLog).filter_by(action="subscription.activated").one()
    assert log.actor_type == "user" and log.user_id == 1
    assert json.loads(log.meta_json)["correlation_id"] == "correlation-1"


def test_provider_actor_not_falsely_assigned_to_human(db):
    sub = make_subscription(db)
    service(db).activate_subscription(1, sub.id, current_period_end=END,
        actor=SubscriptionActor(actor_type="provider", origin="adapter", correlation_id="event:1"))
    log = db.query(AdminAuditLog).filter_by(action="subscription.activated").one()
    assert log.actor_type == "provider" and log.user_id is None


def test_duplicate_current_subscription_uses_database_constraint(db):
    original = make_subscription(db, Status.EXPIRED)
    with pytest.raises(BillingConflict, match="subscription_creation_conflict"):
        service(db).create_subscription(1, plan_id(db, "pro"))
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(Subscription(tenant_id=1, plan_id=plan_id(db)))
        db.flush()
    assert db.query(Subscription).count() == 1
    assert db.query(Subscription).one().id == original.id


def test_concurrent_subscription_creation_cannot_grant_two_current_rows(file_engine):
    with Session(file_engine) as db:
        selected_plan = plan_id(db)
    barrier = Barrier(2)
    def worker():
        barrier.wait(timeout=5)
        for attempt in range(5):
            try:
                with Session(file_engine) as db:
                    sub = service(db).create_subscription(1, selected_plan)
                    return "created", sub.id
            except BillingConflict:
                return "conflict", None
            except OperationalError as exc:
                if "locked" not in str(exc).lower():
                    raise
                time.sleep(0.02 * (attempt + 1))
        raise AssertionError("SQLite did not release its concurrent writer lock")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: worker(), range(2)))
    assert sorted(status for status, _ in results) == ["conflict", "created"]
    with Session(file_engine) as db:
        assert db.query(Subscription).count() == 1
        assert db.query(AdminAuditLog).filter_by(action="subscription.created").count() == 1


def test_stale_version_is_rejected_without_overwriting(db):
    sub = make_subscription(db, Status.ACTIVE)
    old_version = sub.version
    service(db).change_plan(1, sub.id, plan_id(db, "operation"), expected_version=old_version)
    with pytest.raises(BillingConflict, match="stale_subscription_version"):
        service(db).change_plan(1, sub.id, plan_id(db, "pro"), expected_version=old_version)
    assert sub.plan_id == plan_id(db, "operation")


def test_database_optimistic_version_rejects_lost_update(file_engine):
    with Session(file_engine) as db:
        sub_id = make_subscription(db, Status.ACTIVE).id
    with Session(file_engine) as first, Session(file_engine) as second:
        left = first.get(Subscription, sub_id)
        right = second.get(Subscription, sub_id)
        left.cancel_at_period_end = True
        first.commit()
        right.status = Status.PAST_DUE
        with pytest.raises(StaleDataError):
            second.commit()
        second.rollback()
        assert second.get(Subscription, sub_id).status == Status.ACTIVE


def test_atomic_audit_failure_rolls_back_subscription_mutation(db, monkeypatch):
    sub = make_subscription(db)
    def fail(*args, **kwargs):
        raise RuntimeError("audit_unavailable")
    monkeypatch.setattr("app.services.subscriptions.log_admin_action", fail)
    with pytest.raises(RuntimeError, match="audit_unavailable"):
        service(db).activate_subscription(1, sub.id, current_period_end=END)
    assert sub.status == Status.INACTIVE
    assert db.query(AdminAuditLog).count() == 1


def test_outer_transaction_rollback_preserves_atomicity_even_on_sqlite(file_engine):
    with Session(file_engine) as db:
        with pytest.raises(RuntimeError, match="rollback_all"), db.begin():
            sub = service(db).create_subscription(1, 1)
            event = receipt(db).event
            BillingInboxService(db).link_event(event.id, 1, subscription_id=sub.id, now=NOW)
            raise RuntimeError("rollback_all")
    with Session(file_engine) as db:
        assert db.query(Subscription).count() == 0
        assert db.query(AdminAuditLog).count() == 0
        assert db.query(BillingEvent).count() == 0


def test_event_correlates_by_internal_ids_and_rejects_cross_tenant(db):
    sub = make_subscription(db, provider="kiwify")
    checkout = intent(db)
    event = receipt(db).event
    inbox = BillingInboxService(db)
    with pytest.raises(BillingError, match="subscription_not_found"):
        inbox.link_event(event.id, 2, subscription_id=sub.id, now=NOW)
    with pytest.raises(BillingError, match="intent_not_found"):
        inbox.link_event(event.id, 2, checkout_intent_id=checkout.id, now=NOW)
    linked = inbox.link_event(event.id, 1, subscription_id=sub.id, checkout_intent_id=checkout.id, now=NOW)
    assert linked.tenant_id == 1 and linked.subscription_id == sub.id and linked.checkout_intent_id == checkout.id
    with pytest.raises(BillingError, match="event_tenant_mismatch"):
        inbox.link_event(event.id, 2, now=NOW)
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(text("UPDATE billing_events SET tenant_id=2 WHERE id=:id"), {"id": event.id})


@pytest.mark.parametrize("changes", [{"provider": "other"}, {"environment": "production"}, {"provider_account_id": "account-2"}])
def test_intent_event_scope_must_match(db, changes):
    checkout = intent(db)
    event = receipt(db, **changes).event
    with pytest.raises(BillingError, match="event_intent_scope_mismatch"):
        BillingInboxService(db).link_event(event.id, 1, checkout_intent_id=checkout.id, now=NOW)


def test_audit_endpoint_reads_automatic_and_human_rows_compatibly(db):
    make_subscription(db)
    log_admin_action(db, tenant_id=1, user_id=1, action="legacy.action")
    log_admin_action(db, tenant_id=1, user_id=None, actor_type="provider", action="provider.action")
    db.commit()
    app = FastAPI()
    app.include_router(audit_router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[require_admin_user] = lambda: SimpleNamespace(id=1, tenant_id=1, role="admin")
    with TestClient(app) as client:
        response = client.get("/api/admin/audit")
    assert response.status_code == 200
    rows = {row["action"]: row for row in response.json()}
    assert rows["subscription.created"]["user_id"] is None
    assert rows["subscription.created"]["actor_type"] == "system"
    assert rows["legacy.action"]["user_id"] == 1
    assert rows["legacy.action"]["actor_type"] == "user"
    assert rows["provider.action"]["user_id"] is None
    assert rows["provider.action"]["actor_type"] == "provider"


def test_legacy_tenant_stays_unsubscribed_after_billing_metadata(db):
    intent(db)
    receipt(db)
    BillingCatalogService(db).create_mapping(**mapping_args(db))
    for tenant_id in (1, 2):
        result = EntitlementService(db).evaluate(tenant_id, "tracking", now=NOW)
        assert result.allowed and result.reason == "legacy_no_subscription"
    assert db.query(Subscription).count() == 0


def test_checkout_binding_is_unique_in_scope_immutable_and_preserved_on_completion(db):
    first, second = intent(db), intent(db)
    catalog = BillingCatalogService(db)
    catalog.bind_checkout(1, first.public_token, "checkout-1", now=NOW)
    catalog.bind_checkout(1, first.public_token, "checkout-1", now=NOW)
    with pytest.raises(BillingConflict, match="checkout_binding_conflict"):
        catalog.bind_checkout(1, first.public_token, "checkout-changed", now=NOW)
    with pytest.raises(BillingConflict, match="checkout_binding_conflict"):
        catalog.bind_checkout(1, second.public_token, "checkout-1", now=NOW)
    catalog.complete_intent(1, first.public_token, external_subscription_id="subscription-1", now=NOW)
    assert first.external_checkout_id == "checkout-1"
    assert second.external_checkout_id is None


def test_event_links_cannot_be_replaced_with_another_intent(db):
    first, second = intent(db), intent(db)
    event = receipt(db).event
    inbox = BillingInboxService(db)
    inbox.link_event(event.id, 1, checkout_intent_id=first.id, now=NOW)
    with pytest.raises(BillingConflict, match="event_link_conflict"):
        inbox.link_event(event.id, 1, checkout_intent_id=second.id, now=NOW)
    assert event.checkout_intent_id == first.id


def test_all_subscription_mutations_inside_outer_transaction_are_rolled_back(file_engine):
    with Session(file_engine) as db:
        sub = make_subscription(db)
        sub_id = sub.id
    with Session(file_engine) as db:
        with pytest.raises(RuntimeError), db.begin():
            svc = service(db)
            svc.activate_subscription(1, sub_id, current_period_end=END)
            svc.mark_past_due(1, sub_id)
            svc.cancel_subscription(1, sub_id)
            raise RuntimeError("abort")
    with Session(file_engine) as db:
        assert db.get(Subscription, sub_id).status == Status.INACTIVE
        assert db.query(AdminAuditLog).count() == 1


def test_subscription_creation_rolls_back_when_audit_cannot_be_saved(db, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("audit_unavailable")
    monkeypatch.setattr("app.services.subscriptions.log_admin_action", fail)
    with pytest.raises(RuntimeError):
        service(db).create_subscription(1, plan_id(db))
    assert db.query(Subscription).count() == 0
    assert db.query(AdminAuditLog).count() == 0


def test_adding_subscription_revalidates_already_linked_completed_intent(db):
    checkout = intent(db)
    BillingCatalogService(db).complete_intent(1, checkout.public_token, external_subscription_id="external-correct", now=NOW)
    sub = service(db).create_subscription(1, plan_id(db), provider="kiwify", provider_subscription_id="external-wrong")
    event = receipt(db).event
    inbox = BillingInboxService(db)
    inbox.link_event(event.id, 1, checkout_intent_id=checkout.id, now=NOW)
    with pytest.raises(BillingError, match="event_subscription_binding_mismatch"):
        inbox.link_event(event.id, 1, subscription_id=sub.id, now=NOW)
    assert event.checkout_intent_id == checkout.id and event.subscription_id is None
