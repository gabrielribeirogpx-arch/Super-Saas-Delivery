import pytest
import sqlalchemy as sa
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from app.core.database import Base
from app.models.tenant import Tenant
from app.models.order import Order
from app.models.order_durability import OrderOutbox
from test_billing_phase2_migrations import config, preserve_logging

OLD = "20261023_01_admin_recovery"
HEAD = "20261023_02_order_durability"
TABLES = {"order_submissions", "order_outbox", "order_effect_receipts"}


def test_migration_preserves_legacy_orders_matches_models_and_guards_history(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path/'migration.db'}")
    Base.metadata.create_all(engine, tables=[t for t in Base.metadata.sorted_tables if t.name not in TABLES])
    with engine.begin() as connection:
        connection.execute(Tenant.__table__.insert().values(id=1, slug="preserved"))
        connection.execute(Order.__table__.insert().values(id=1, tenant_id=1, cliente_telefone="fixture", itens="preserve", total_cents=1500))
    cfg = config(str(engine.url))
    command.stamp(cfg, OLD)
    command.upgrade(cfg, HEAD)
    def include(obj, name, kind, reflected, compared):
        table = obj if kind == "table" else getattr(obj, "table", None)
        return table is None or table.name in TABLES
    with engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection, opts={"include_object": include}), Base.metadata) == []
        assert connection.execute(sa.text("SELECT itens FROM orders WHERE id=1")).scalar_one() == "preserve"
    command.downgrade(cfg, OLD)
    assert not TABLES & set(sa.inspect(engine).get_table_names())
    command.upgrade(cfg, HEAD)
    from sqlalchemy.orm import Session
    with Session(engine) as db, db.begin():
        db.add(OrderOutbox(tenant_id=1, order_id=1, event_key="x" * 32,
            effect="whatsapp.created", stream="whatsapp", payload={"status": "RECEBIDO"}))
    with pytest.raises(RuntimeError, match="Archive order durability history"):
        command.downgrade(cfg, OLD)
    assert TABLES <= set(sa.inspect(engine).get_table_names())
    engine.dispose()
