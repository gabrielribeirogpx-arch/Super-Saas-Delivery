from dataclasses import replace

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

import app.models
from app.core.database import Base
from app.models.finance import CashMovement, OrderPayment
from app.models.native_payment import (
    NativePaymentAttempt, NativePaymentEvent, NativePaymentIntent, NativePaymentLedger,
)
from app.models.order import Order
from app.models.tenant import Tenant
from app.services.commercial_policy import (
    CommercialContext, FeeRule, OrderAmounts, PaymentMethod, PlanCode, SalesChannel,
)
from app.services.fake_native_payments import FakePaymentEvent, PaymentState
from app.services.sandbox_payment_store import SandboxPaymentStore


@pytest.fixture
def database(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'native.db'}")
    @sa.event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db, db.begin():
        db.add_all([Tenant(id=1, slug="simulation-one"), Tenant(id=2, slug="simulation-two")])
        db.flush()
        db.add_all([
            Order(id=1, tenant_id=1, cliente_telefone="fixture", itens="fixture", total_cents=10_000),
            Order(id=2, tenant_id=2, cliente_telefone="fixture", itens="fixture", total_cents=10_000),
            Order(id=3, tenant_id=1, cliente_telefone="fixture", itens="fixture", total_cents=10_000),
        ])
    yield engine, sessions
    engine.dispose()


def store(db):
    return SandboxPaymentStore(db, runtime_environment="test", simulation_enabled=True)


def create(db, tenant_id=1, order_id=1, key="request-1", **rule_overrides):
    context = CommercialContext(tenant_id, PlanCode.FREE, SalesChannel.OWN_STORE)
    values = dict(version="fixture-v1", plan_code=context.plan_code, channel=context.channel,
                  payment_method=PaymentMethod.NATIVE_PIX, rate_bps=200, fixed_cents=20)
    values.update(rule_overrides)
    return store(db).create(context, order_id, OrderAmounts(10_000), FeeRule(**values), key)


def event(intent, state, event_id="event-1", **changes):
    values = dict(event_id=event_id, payment_id=intent.public_id,
                  tenant_id=intent.tenant_id, amount_cents=intent.total_cents, state=state)
    values.update(changes)
    return FakePaymentEvent(**values)


def test_pending_intent_and_attempt_survive_new_session_without_legacy_money(database):
    _, sessions = database
    with sessions() as db, db.begin():
        intent = create(db)
        public_id = intent.public_id
        assert intent.status == "pending"
        assert intent.environment == "sandbox"
        assert intent.provider == "internal_simulation"
        assert intent.settlement_status == "not_settled"
        assert intent.paid_at is None
        assert db.query(NativePaymentAttempt).one().status == "pending"
        assert db.query(OrderPayment).count() == db.query(CashMovement).count() == 0
    with sessions() as db:
        intent = store(db).get(1, public_id)
        assert intent.status == "pending"
        assert intent.snapshot["rule"]["version"] == "fixture-v1"
        assert intent.total_cents == 10_000
        assert store(db).ledger_for_tenant(1) == ()


def test_creation_replay_is_durable_and_changed_fee_or_second_key_is_refused(database):
    _, sessions = database
    with sessions() as db, db.begin():
        public_id = create(db).public_id
    with sessions() as db, db.begin():
        assert create(db).public_id == public_id
        with pytest.raises(ValueError, match="idempotency_conflict"):
            create(db, rate_bps=300)
        with pytest.raises(ValueError, match="order_already_has_intent"):
            create(db, key="other")
        assert db.query(NativePaymentIntent).count() == 1
        assert db.query(NativePaymentAttempt).count() == 1


def test_idempotency_keys_are_tenant_scoped_and_get_does_not_leak(database):
    _, sessions = database
    with sessions() as db, db.begin():
        first = create(db)
        second = create(db, tenant_id=2, order_id=2)
        assert first.public_id != second.public_id
        with pytest.raises(ValueError, match="payment_not_found"):
            store(db).get(2, first.public_id)
        with pytest.raises(ValueError, match="payment_not_found"):
            store(db).apply_simulated_event(event(first, PaymentState.PAID, tenant_id=2))
        with pytest.raises(ValueError, match="order_not_found"):
            create(db, tenant_id=1, order_id=2, key="foreign-order")


def test_payment_and_refund_replay_remain_idempotent_after_process_restart(database):
    _, sessions = database
    with sessions() as db, db.begin():
        intent = create(db)
        public_id = intent.public_id
        paid = event(intent, PaymentState.PAID, "paid")
        assert store(db).apply_simulated_event(paid).status == "paid"
    with sessions() as db, db.begin():
        intent = store(db).get(1, public_id)
        store(db).apply_simulated_event(paid)
        store(db).apply_simulated_event(event(intent, PaymentState.PAID, "paid-alias"))
        assert len(store(db).ledger_for_tenant(1)) == 1
        assert intent.settlement_status == "not_settled"
        assert intent.paid_at is not None
        refund = event(intent, PaymentState.REFUNDED, "refund")
        store(db).apply_simulated_event(refund)
    with sessions() as db, db.begin():
        store(db).apply_simulated_event(refund)
        assert store(db).apply_simulated_event(paid).status == "refunded"
        entries = store(db).ledger_for_tenant(1)
        assert len(entries) == 2
        assert sum(x.gross_delta_cents for x in entries) == 0
        assert sum(x.platform_fee_delta_cents for x in entries) == 0
        assert sum(x.merchant_delta_cents for x in entries) == 0
        assert store(db).ledger_for_tenant(2) == ()
        with pytest.raises(ValueError, match="invalid_payment_transition"):
            store(db).apply_simulated_event(replace(paid, event_id="late-paid"))
        assert db.query(OrderPayment).count() == db.query(CashMovement).count() == 0


def test_caller_rollback_undoes_intent_creation_even_when_savepoint_is_first_write(database):
    _, sessions = database
    with sessions() as db:
        create(db)
        db.rollback()
    with sessions() as db:
        assert db.query(NativePaymentIntent).count() == 0
        assert db.query(NativePaymentAttempt).count() == 0


def test_caller_rollback_undoes_status_event_and_ledger_together(database):
    _, sessions = database
    with sessions() as db, db.begin():
        public_id = create(db).public_id
    with sessions() as db:
        intent = store(db).get(1, public_id)
        store(db).apply_simulated_event(event(intent, PaymentState.PAID))
        db.rollback()
    with sessions() as db:
        assert store(db).get(1, public_id).status == "pending"
        assert db.query(NativePaymentEvent).count() == db.query(NativePaymentLedger).count() == 0
        assert db.query(NativePaymentAttempt).one().status == "pending"


def test_event_id_reuse_for_another_intent_and_wrong_amount_are_refused(database):
    _, sessions = database
    with sessions() as db, db.begin():
        first = create(db)
        second = create(db, order_id=3, key="second")
        with pytest.raises(ValueError, match="payment_amount_or_currency_mismatch"):
            store(db).apply_simulated_event(event(first, PaymentState.PAID, amount_cents=9_999))
        store(db).apply_simulated_event(event(first, PaymentState.PAID))
        with pytest.raises(ValueError, match="event_id_conflict"):
            store(db).apply_simulated_event(event(second, PaymentState.PAID))
        assert second.status == "pending"
        assert db.query(NativePaymentLedger).count() == 1


@pytest.mark.parametrize("terminal", [PaymentState.FAILED, PaymentState.CANCELED])
def test_terminal_failure_does_not_generate_a_financial_receipt(database, terminal):
    _, sessions = database
    with sessions() as db, db.begin():
        intent = create(db)
        store(db).apply_simulated_event(event(intent, terminal))
        with pytest.raises(ValueError, match="invalid_payment_transition"):
            store(db).apply_simulated_event(event(intent, PaymentState.PAID, "late"))
        assert db.query(NativePaymentLedger).count() == 0


def test_existing_legacy_payment_blocks_a_parallel_native_intent(database):
    _, sessions = database
    with sessions() as db, db.begin():
        db.add(OrderPayment(tenant_id=1, order_id=1, method="pix", amount_cents=10_000, status="paid"))
    with sessions() as db, db.begin():
        with pytest.raises(ValueError, match="legacy_payment_exists"):
            create(db)
        assert db.query(NativePaymentIntent).count() == 0


def test_store_refuses_invalid_total_and_corrupt_persisted_quote(database):
    _, sessions = database
    with sessions() as db, db.begin():
        db.query(Order).filter_by(id=1).update({"total_cents": 12_000})
    with sessions() as db, db.begin():
        with pytest.raises(ValueError, match="order_total_mismatch"):
            create(db)
        intent = create(db, order_id=3)
        intent.snapshot_hash = "0" * 64
        db.flush()
        with pytest.raises(ValueError, match="invalid_snapshot"):
            store(db).apply_simulated_event(event(intent, PaymentState.PAID))
        assert intent.status == "pending"
        assert db.query(NativePaymentLedger).count() == 0


def test_database_composite_foreign_keys_reject_cross_tenant_attempt(database):
    _, sessions = database
    with sessions() as db, db.begin():
        intent = create(db)
        with pytest.raises(IntegrityError):
            with db.begin_nested():
                db.add(NativePaymentAttempt(tenant_id=2, intent_id=intent.id, attempt_number=2, idempotency_key="wrong-owner"))
                db.flush()
        assert db.query(NativePaymentAttempt).count() == 1


def test_database_composite_order_fk_rejects_wrong_owner(database):
    _, sessions = database
    with sessions() as db, db.begin():
        intent = create(db)
        with pytest.raises(IntegrityError):
            with db.begin_nested():
                db.execute(sa.update(NativePaymentIntent).where(NativePaymentIntent.id == intent.id).values(order_id=2))
        db.refresh(intent)
        assert intent.order_id == 1


def test_ledger_event_cannot_be_attached_to_a_different_intent(database):
    _, sessions = database
    with sessions() as db, db.begin():
        first = create(db)
        second = create(db, order_id=3, key="second")
        store(db).apply_simulated_event(event(first, PaymentState.PAID))
        record = db.query(NativePaymentEvent).one()
        with pytest.raises(IntegrityError):
            with db.begin_nested():
                db.add(NativePaymentLedger(
                    tenant_id=1, intent_id=second.id, event_id=record.id, kind="payment",
                    gross_delta_cents=10_000, platform_fee_delta_cents=220, merchant_delta_cents=9_780,
                ))
                db.flush()


@pytest.mark.parametrize("environment,enabled", [("production", True), ("dev", True), ("staging", False), ("test", False)])
def test_simulation_requires_explicit_non_production_runtime(database, environment, enabled):
    _, sessions = database
    with sessions() as db:
        with pytest.raises(ValueError, match="simulation_not_enabled"):
            SandboxPaymentStore(db, runtime_environment=environment, simulation_enabled=enabled)
