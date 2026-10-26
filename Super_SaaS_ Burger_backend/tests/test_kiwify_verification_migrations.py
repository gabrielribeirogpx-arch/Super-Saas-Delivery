from io import StringIO

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
import pytest
import sqlalchemy as sa

from test_billing_phase2_migrations import phase1_db, config, preserve_logging
from app.core.database import Base

OLD = "20261006_07_billing_audit"
HEAD = "20261007_01_billing_verification"


def test_verification_migration_roundtrip_and_schema(phase1_db):
    engine, cfg = phase1_db
    command.upgrade(cfg, OLD)
    with engine.begin() as conn:
        conn.execute(sa.text("INSERT INTO billing_events(provider,environment,provider_account_id,provider_event_id,event_type,payload_hash,raw_payload) VALUES ('internal','sandbox','account','old','paid',:hash,'{}')"), {"hash": "a"*64})
    command.upgrade(cfg, HEAD)
    def include(obj, name, kind, reflected, compared):
        table = obj if kind == "table" else getattr(obj, "table", None)
        return table is None or table.name in {"billing_events", "billing_provider_budgets"}
    with engine.connect() as conn:
        assert compare_metadata(MigrationContext.configure(conn, opts={"include_object": include, "compare_type": True}), Base.metadata) == []
        assert conn.execute(sa.text("SELECT verification_status,verification_attempts FROM billing_events")).one() == ("pending", 0)
        assert conn.execute(sa.text("PRAGMA foreign_key_check")).all() == []
    command.downgrade(cfg, OLD)
    assert "billing_provider_budgets" not in sa.inspect(engine).get_table_names()
    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT provider_event_id FROM billing_events")).scalar_one() == "old"
    command.upgrade(cfg, HEAD)


def test_verification_downgrade_refuses_to_erase_trust_boundary(phase1_db):
    engine, cfg = phase1_db
    command.upgrade(cfg, HEAD)
    with engine.begin() as conn:
        conn.execute(sa.text("INSERT INTO billing_events(provider,environment,provider_account_id,provider_event_id,event_type,payload_hash,raw_payload,schema_version) VALUES ('kiwify','sandbox','account','new','paid',:hash,'{}',2)"), {"hash": "a"*64})
    with pytest.raises(RuntimeError, match="Archive Kiwify"):
        command.downgrade(cfg, OLD)
    assert "verification_status" in {c["name"] for c in sa.inspect(engine).get_columns("billing_events")}
    assert "billing_provider_budgets" in sa.inspect(engine).get_table_names()


def test_verification_postgres_sql():
    output = StringIO()
    cfg = config("postgresql+psycopg://unused:unused@localhost/unused", output)
    command.upgrade(cfg, f"{OLD}:{HEAD}", sql=True)
    assert "ADD COLUMN verification_status" in output.getvalue()
    assert "CREATE TABLE billing_provider_budgets" in output.getvalue()
    output = StringIO()
    cfg = config("postgresql+psycopg://unused:unused@localhost/unused", output)
    command.downgrade(cfg, f"{HEAD}:{OLD}", sql=True)
    assert "Archive Kiwify verification receipts" in output.getvalue()
