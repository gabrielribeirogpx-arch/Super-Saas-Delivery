from io import StringIO

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy.orm import Session

import app.models
from app.core.database import Base
from app.models.order import Order
from app.models.tenant import Tenant
from test_billing_phase2_migrations import config, preserve_logging

OLD = "20261007_02_billing_review"
HEAD = "20261018_01_native_payments"
TABLES = ("native_payment_ledger", "native_payment_events", "native_payment_attempts", "native_payment_intents")


@pytest.fixture
def migrated_database(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'native-migration.db'}")
    @sa.event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine, tables=[t for t in Base.metadata.sorted_tables
        if t.name not in {"order_submissions", "order_outbox", "order_effect_receipts"}])
    with engine.begin() as conn:
        for table in TABLES:
            Base.metadata.tables[table].drop(conn)
        conn.exec_driver_sql("DROP INDEX uq_orders_id_tenant")
    with Session(engine) as db, db.begin():
        db.add(Tenant(id=1, slug="migration-sentinel"))
        db.flush()
        db.add(Order(id=1, tenant_id=1, cliente_telefone="fixture", itens="preserve-me", total_cents=1_000))
    cfg = config(str(engine.url))
    command.stamp(cfg, OLD)
    yield engine, cfg
    engine.dispose()


def test_native_migration_roundtrip_schema_parity_and_legacy_preservation(migrated_database):
    engine, cfg = migrated_database
    command.upgrade(cfg, HEAD)
    def include(obj, name, kind, reflected, compared):
        table = obj if kind == "table" else getattr(obj, "table", None)
        return table is None or table.name in set(TABLES) | {"orders"}
    with engine.connect() as conn:
        assert compare_metadata(MigrationContext.configure(conn, opts={"include_object": include, "compare_type": True}), Base.metadata) == []
        assert conn.exec_driver_sql("PRAGMA foreign_key_check").all() == []
        assert conn.execute(sa.text("SELECT itens FROM orders WHERE id=1")).scalar_one() == "preserve-me"
    command.downgrade(cfg, OLD)
    assert not set(TABLES) & set(sa.inspect(engine).get_table_names())
    assert "uq_orders_id_tenant" not in {x["name"] for x in sa.inspect(engine).get_indexes("orders")}
    command.upgrade(cfg, HEAD)
    assert set(TABLES) <= set(sa.inspect(engine).get_table_names())
    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT itens FROM orders WHERE id=1")).scalar_one() == "preserve-me"


def test_postgresql_offline_upgrade_and_history_guard():
    output = StringIO()
    cfg = config("postgresql+psycopg://unused:unused@localhost/unused", output)
    command.upgrade(cfg, f"{OLD}:{HEAD}", sql=True)
    sql = output.getvalue()
    for table in TABLES:
        assert f"CREATE TABLE {table}" in sql
    assert "CREATE UNIQUE INDEX uq_orders_id_tenant" in sql
    assert "FOREIGN KEY(order_id, tenant_id) REFERENCES orders" in sql
    output = StringIO()
    cfg = config("postgresql+psycopg://unused:unused@localhost/unused", output)
    command.downgrade(cfg, f"{HEAD}:{OLD}", sql=True)
    assert "Archive native payment history before downgrade" in output.getvalue()
