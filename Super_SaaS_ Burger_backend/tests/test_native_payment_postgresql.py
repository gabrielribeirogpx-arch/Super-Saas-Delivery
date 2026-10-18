"""Opt-in integration tests, run by the dedicated disposable PostgreSQL CI job."""
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

import app.models
from app.core.database import Base
from app.models.native_payment import NativePaymentAttempt, NativePaymentEvent, NativePaymentIntent, NativePaymentLedger
from app.models.order import Order
from app.models.tenant import Tenant
from app.services.fake_native_payments import PaymentState
from test_billing_phase2_migrations import config, preserve_logging
from test_sandbox_payment_store import create, event, store

OLD = "20261007_02_billing_review"
HEAD = "20261018_01_native_payments"
TABLES = ("native_payment_ledger", "native_payment_events", "native_payment_attempts", "native_payment_intents")


@pytest.fixture
def pg_database():
    raw = os.getenv("NATIVE_PAYMENTS_TEST_DATABASE_URL")
    if not raw:
        pytest.skip("Explicit disposable PostgreSQL test URL required")
    url = make_url(raw)
    if url.host not in {"localhost", "127.0.0.1"} or url.database != "native_payments_ci":
        pytest.fail("Refusing non-local/non-dedicated native payment test database")
    schema = f"native_test_{uuid4().hex}"
    admin = sa.create_engine(url)
    engine = None
    with admin.begin() as conn:
        conn.execute(sa.schema.CreateSchema(schema))
    try:
        scoped = url.update_query_dict({"options": f"-csearch_path={schema}"})
        engine = sa.create_engine(scoped)
        Base.metadata.create_all(engine)
        with engine.begin() as conn:
            for table in TABLES:
                Base.metadata.tables[table].drop(conn)
            conn.exec_driver_sql("DROP INDEX uq_orders_id_tenant")
        cfg = config(scoped.render_as_string(hide_password=False).replace("%", "%%"))
        command.stamp(cfg, OLD)
        command.upgrade(cfg, HEAD)
        sessions = sessionmaker(bind=engine, expire_on_commit=False)
        with sessions() as db, db.begin():
            db.add_all([Tenant(id=1, slug="pg-sim-one"), Tenant(id=2, slug="pg-sim-two")])
            db.flush()
            db.add_all([
                Order(id=1, tenant_id=1, cliente_telefone="fixture", itens="preserve", total_cents=10_000),
                Order(id=2, tenant_id=2, cliente_telefone="fixture", itens="preserve", total_cents=10_000),
                Order(id=3, tenant_id=1, cliente_telefone="fixture", itens="preserve", total_cents=10_000),
            ])
        yield engine, sessions, cfg
    finally:
        if engine is not None:
            engine.dispose()
        with admin.begin() as conn:
            conn.execute(sa.schema.DropSchema(schema, cascade=True))
        admin.dispose()


def test_pg_upgrade_downgrade_and_legacy_order_preservation(pg_database):
    engine, sessions, cfg = pg_database
    command.downgrade(cfg, OLD)
    assert not set(TABLES) & set(sa.inspect(engine).get_table_names())
    command.upgrade(cfg, HEAD)
    assert set(TABLES) <= set(sa.inspect(engine).get_table_names())
    with sessions() as db:
        assert db.query(Order).filter_by(id=1).one().itens == "preserve"


def test_pg_same_order_concurrent_create_is_one_intent_and_attempt(pg_database):
    _, sessions, _ = pg_database
    barrier = Barrier(2)
    def worker():
        with sessions() as db, db.begin():
            barrier.wait(timeout=15)
            return create(db).public_id
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker) for _ in range(2)]
        ids = [future.result(timeout=30) for future in futures]
    assert ids[0] == ids[1]
    with sessions() as db:
        assert db.query(NativePaymentIntent).count() == 1
        assert db.query(NativePaymentAttempt).count() == 1


@pytest.mark.parametrize("same_event_id", [True, False])
def test_pg_concurrent_confirmation_never_duplicates_ledger(pg_database, same_event_id):
    _, sessions, _ = pg_database
    with sessions() as db, db.begin():
        intent = create(db)
        events = [event(intent, PaymentState.PAID, "approval" if same_event_id else f"approval-{i}") for i in range(2)]
    barrier = Barrier(2)
    def worker(incoming):
        with sessions() as db, db.begin():
            barrier.wait(timeout=15)
            return store(db).apply_simulated_event(incoming).status
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, incoming) for incoming in events]
        assert [f.result(timeout=30) for f in futures] == ["paid", "paid"]
    with sessions() as db:
        assert db.query(NativePaymentLedger).count() == 1
        assert db.query(NativePaymentEvent).count() == (1 if same_event_id else 2)
        assert db.query(NativePaymentIntent).one().settlement_status == "not_settled"


def test_pg_same_key_on_different_orders_rolls_back_the_losing_intent(pg_database):
    _, sessions, _ = pg_database
    barrier = Barrier(2)
    def worker(order_id):
        try:
            with sessions() as db, db.begin():
                barrier.wait(timeout=15)
                create(db, order_id=order_id)
            return "created"
        except ValueError as exc:
            assert str(exc) in {"idempotency_conflict", "payment_creation_conflict"}
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, order_id) for order_id in (1, 3)]
        assert sorted(f.result(timeout=30) for f in futures) == ["conflict", "created"]
    with sessions() as db:
        assert db.query(NativePaymentIntent).count() == db.query(NativePaymentAttempt).count() == 1


def test_pg_tenant_foreign_key_and_history_downgrade_guard(pg_database):
    engine, sessions, cfg = pg_database
    with sessions() as db, db.begin():
        intent = create(db)
        with pytest.raises(IntegrityError):
            with db.begin_nested():
                db.add(NativePaymentAttempt(tenant_id=2, intent_id=intent.id, attempt_number=2, idempotency_key="cross"))
                db.flush()
    with pytest.raises(RuntimeError, match="Archive native payment history"):
        command.downgrade(cfg, OLD)
    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one() == HEAD
        assert conn.execute(sa.text("SELECT count(*) FROM native_payment_intents")).scalar_one() == 1
