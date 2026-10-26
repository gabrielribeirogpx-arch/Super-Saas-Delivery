import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from test_billing_phase2 import database
from app.models.menu_item import MenuItem
from app.models.tenant import Tenant
from app.models.order import Order
from app.models.customer_stats import CustomerStats
from app.models.finance import OrderPayment
from app.models.order_durability import OrderSubmission, OrderOutbox, OrderEffectReceipt
from app.routers import public_menu
from app.services.order_outbox import enqueue_order_created, enqueue_order_status_changed
from app.services import order_outbox_worker as worker
from app.services.order_idempotency import make_attempt

NOW = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)
KEY = "synthetic-attempt-key-0000000000000001"


@pytest.fixture
def sessions(tmp_path, monkeypatch):
    # Queue timestamps and the worker's test clock must share the same time,
    # regardless of the calendar date on which this suite is executed.
    from app.models import order_durability
    class QueueClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW if tz is not None else NOW.replace(tzinfo=None)
    monkeypatch.setattr(order_durability, "datetime", QueueClock)
    monkeypatch.setattr(worker, "datetime", QueueClock)
    engine = database(create_engine(f"sqlite:///{tmp_path / 'orders.db'}", connect_args={"check_same_thread": False, "timeout": 10}))
    factory = sessionmaker(bind=engine)
    with factory() as db, db.begin():
        db.add_all([MenuItem(id=1, tenant_id=1, name="Item 1", price_cents=1500),
                    MenuItem(id=2, tenant_id=2, name="Item 2", price_cents=2500)])
    async def no_network(_):
        return None, None
    monkeypatch.setattr(public_menu, "geocode_address", no_network)
    yield factory
    engine.dispose()


def payload(tenant=1, **extra):
    return public_menu.PublicOrderPayload(customer_name="Cliente sintético", customer_phone="11999999999",
        order_type="pickup", delivery_type="RETIRADA", payment_method="money",
        items=[{"item_id": tenant, "quantity": 1}], **extra)


def submit(sessions, *, tenant=1, key=KEY, **extra):
    with sessions() as db:
        return asyncio.run(public_menu._create_order_for_tenant(db, db.get(Tenant, tenant),
            payload(tenant, **extra), idempotency_key=key))


def test_lost_response_and_repeated_attempt_replay_one_order_and_one_effect(sessions):
    first = submit(sessions)
    second = submit(sessions)
    assert second.model_dump() == first.model_dump()
    with sessions() as db:
        assert db.query(Order).count() == db.query(OrderSubmission).count() == db.query(OrderOutbox).count() == 1
        row = db.query(OrderOutbox).one()
        assert row.effect == "whatsapp.created" and row.status == "pending"
        assert set(row.payload) == {"status", "previous_status", "assigned_delivery_user_id"}
        assert "Cliente" not in str(row.payload) and KEY not in str(db.query(OrderSubmission).one().__dict__)


def test_same_key_changed_payload_conflicts_and_other_store_is_independent(sessions):
    first = submit(sessions)
    with pytest.raises(Exception) as error:
        submit(sessions, notes="Dados diferentes")
    assert error.value.status_code == 409
    other = submit(sessions, tenant=2)
    assert other.tracking_token != first.tracking_token
    with sessions() as db:
        assert db.query(Order).count() == 2 and db.query(OrderSubmission).count() == 2


def test_order_failure_rolls_back_receipt_order_and_tasks_then_same_key_can_retry(sessions, monkeypatch):
    original = public_menu.create_order_items
    def fail(*_, **__):
        raise RuntimeError("synthetic persistence failure")
    monkeypatch.setattr(public_menu, "create_order_items", fail)
    with pytest.raises(RuntimeError):
        submit(sessions)
    with sessions() as db:
        assert db.query(Order).count() == db.query(OrderSubmission).count() == db.query(OrderOutbox).count() == 0
    monkeypatch.setattr(public_menu, "create_order_items", original)
    assert submit(sessions).tracking_token


@pytest.mark.parametrize("key", ["short", "!" * 32, "x" * 129])
def test_invalid_key_creates_nothing(sessions, key):
    with pytest.raises(Exception) as error:
        submit(sessions, key=key)
    assert error.value.status_code == 400
    with sessions() as db:
        assert db.query(Order).count() == db.query(OrderSubmission).count() == 0


def fake_sender(calls):
    def send(db, **kwargs):
        calls.append(kwargs["template"])
        return SimpleNamespace(status="sent", error=None)
    return send


def test_successful_effect_is_receipted_and_duplicate_event_does_not_resend(sessions, monkeypatch):
    submit(sessions)
    calls = []
    monkeypatch.setattr(worker, "send_whatsapp_message", fake_sender(calls))
    assert worker.run_cycle(sessions, clock=lambda: NOW)["done"] == 1
    with sessions() as db, db.begin():
        enqueue_order_created(db, db.query(Order).one())
    assert worker.run_cycle(sessions, clock=lambda: NOW)["done"] == 1
    assert calls == ["order_confirmed"]
    with sessions() as db:
        assert db.query(OrderEffectReceipt).count() == 1
        assert db.query(OrderOutbox).filter_by(status="done").count() == 2


def test_crash_lease_recovery_and_obsolete_worker_cannot_send_or_ack(sessions, monkeypatch):
    submit(sessions)
    calls = []
    monkeypatch.setattr(worker, "send_whatsapp_message", fake_sender(calls))
    old = worker.claim_one(sessions, NOW)
    assert old is not None and worker.claim_one(sessions, NOW) is None
    later = NOW + worker.LEASE + timedelta(seconds=1)
    current = worker.claim_one(sessions, later)
    assert current.id == old.id and current.token != old.token
    assert worker.dispatch(sessions, old, lambda: later) is False
    assert calls == []
    assert worker.dispatch(sessions, current, lambda: later)
    assert calls == ["order_confirmed"]
    with sessions() as db:
        assert db.query(OrderOutbox).one().attempts == 2


def test_failed_effect_retries_with_backoff_then_enters_review(sessions, monkeypatch):
    submit(sessions)
    def failed(*_, **__):
        return SimpleNamespace(status="failed", error="provider unavailable")
    monkeypatch.setattr(worker, "send_whatsapp_message", failed)
    now = NOW
    for expected in range(1, 9):
        assert worker.run_cycle(sessions, clock=lambda: now)["retry"] == 1
        with sessions() as db:
            row = db.query(OrderOutbox).one()
            assert row.attempts == expected
            now = worker.utc(row.next_attempt_at)
    assert row.status == "review" and row.error_code == "effect_failed"
    assert worker.run_cycle(sessions, clock=lambda: now)["retry"] == 0
    assert worker.stats(sessions)["counts"]["review"] == 1


def test_stats_and_receipt_are_atomic_and_repeated_delivered_does_not_increment(sessions, monkeypatch):
    submit(sessions)
    monkeypatch.setattr(worker, "send_whatsapp_message", fake_sender([]))
    worker.run_cycle(sessions, clock=lambda: NOW)
    for _ in range(2):
        with sessions() as db, db.begin():
            order = db.query(Order).one()
            order.status = "DELIVERED"
            enqueue_order_status_changed(db, order, "OUT_FOR_DELIVERY")
        worker.run_cycle(sessions, clock=lambda: NOW)
    with sessions() as db:
        stats = db.query(CustomerStats).one()
        assert stats.total_orders == 1 and stats.total_spent == 1500
        assert db.query(OrderEffectReceipt).filter_by(effect_key="customer.delivered").count() == 1


def test_status_stream_waits_for_earlier_notification_but_stats_can_progress(sessions, monkeypatch):
    submit(sessions)
    with sessions() as db, db.begin():
        order = db.query(Order).one()
        order.status = "DELIVERED"
        enqueue_order_status_changed(db, order, "OUT_FOR_DELIVERY")
    def failed(*_, **__):
        raise RuntimeError("external failure")
    monkeypatch.setattr(worker, "send_whatsapp_message", failed)
    result = worker.run_cycle(sessions, clock=lambda: NOW)
    assert result["retry"] == 1 and result["done"] == 1
    with sessions() as db:
        assert db.query(OrderOutbox).filter_by(effect="whatsapp.status").one().attempts == 0
        assert db.query(CustomerStats).one().total_orders == 1


def test_queue_and_order_rollback_together(sessions):
    submit(sessions)
    with sessions() as db:
        order = db.query(Order).one()
        order.status = "PRONTO"
        enqueue_order_status_changed(db, order, "RECEBIDO")
        db.rollback()
    with sessions() as db:
        assert db.query(Order).one().status != "PRONTO"
        assert db.query(OrderOutbox).count() == 1


def test_same_attempt_committing_between_replay_and_capacity_check_still_replays(sessions, monkeypatch):
    original = public_menu.require_feature
    entered = False
    committed = []
    def interleaved(db, tenant_id, feature):
        nonlocal entered
        if not entered:
            entered = True
            committed.append(submit(sessions, street="Rua A", number="1"))
            raise HTTPException(403, "capacity was consumed by the identical attempt")
        return original(db, tenant_id, feature)
    monkeypatch.setattr(public_menu, "require_feature", interleaved)
    assert submit(sessions, street="Rua A", number="1").model_dump() == committed[0].model_dump()
    with sessions() as db:
        assert db.query(Order).count() == db.query(OrderSubmission).count() == db.query(OrderOutbox).count() == 1


def test_queue_insert_failure_at_commit_rolls_back_order_finance_and_receipt(sessions, monkeypatch):
    def invalid_job(db, order):
        db.add(OrderOutbox(tenant_id=2, order_id=order.id, event_key="x" * 32,
            effect="whatsapp.created", stream="whatsapp", payload={"status": "RECEBIDO"}))
    monkeypatch.setattr(public_menu, "enqueue_order_created", invalid_job)
    with pytest.raises(IntegrityError):
        submit(sessions)
    with sessions() as db:
        assert db.query(Order).count() == db.query(OrderSubmission).count() == db.query(OrderOutbox).count() == db.query(OrderPayment).count() == 0


def test_replay_after_reservation_releases_the_store_lock_before_returning(sessions):
    first = submit(sessions)
    with sessions() as db:
        data = payload()
        attempt = make_attempt(1, KEY, data)
        replayed = public_menu._persist_order_for_tenant(db, db.get(Tenant, 1), data, attempt=attempt)
        assert not db.in_transaction()
        assert replayed.model_dump() == first.model_dump()
