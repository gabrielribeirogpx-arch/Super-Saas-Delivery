from io import StringIO
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
import pytest
import sqlalchemy as sa

from test_billing_phase2_migrations import phase1_db, config, preserve_logging
from app.core.database import Base

OLD = "20261007_01_billing_verification"
HEAD = "20261007_02_billing_review"


def test_manual_review_migration_roundtrip(phase1_db):
    engine, cfg = phase1_db
    command.upgrade(cfg, OLD)
    command.upgrade(cfg, HEAD)
    def include(obj, name, kind, reflected, compared):
        table = obj if kind == "table" else getattr(obj, "table", None)
        return table is None or table.name == "billing_manual_reviews"
    with engine.connect() as conn:
        assert compare_metadata(MigrationContext.configure(conn, opts={"include_object": include, "compare_type": True}), Base.metadata) == []
        assert conn.execute(sa.text("PRAGMA foreign_key_check")).all() == []
    command.downgrade(cfg, OLD)
    assert "billing_manual_reviews" not in sa.inspect(engine).get_table_names()
    command.upgrade(cfg, HEAD)


def test_manual_review_downgrade_requires_archiving(phase1_db):
    engine, cfg = phase1_db
    command.upgrade(cfg, HEAD)
    with engine.begin() as conn:
        conn.execute(sa.text("INSERT INTO billing_events(provider,environment,provider_account_id,provider_event_id,event_type,payload_hash,raw_payload) VALUES ('internal','sandbox','account','old','paid',:hash,'{}')"), {"hash": "a"*64})
        event_id = conn.execute(sa.text("SELECT id FROM billing_events")).scalar_one()
        conn.execute(sa.text("INSERT INTO billing_manual_reviews(billing_event_id) VALUES (:id)"), {"id": event_id})
    with pytest.raises(RuntimeError, match="Archive billing manual reviews"):
        command.downgrade(cfg, OLD)
    assert "billing_manual_reviews" in sa.inspect(engine).get_table_names()


def test_manual_review_postgres_sql():
    output = StringIO()
    cfg = config("postgresql+psycopg://unused:unused@localhost/unused", output)
    command.upgrade(cfg, f"{OLD}:{HEAD}", sql=True)
    assert "CREATE TABLE billing_manual_reviews" in output.getvalue()
    assert "binding_approved" in output.getvalue()
    output = StringIO()
    cfg = config("postgresql+psycopg://unused:unused@localhost/unused", output)
    command.downgrade(cfg, f"{HEAD}:{OLD}", sql=True)
    assert "Archive billing manual reviews before downgrade" in output.getvalue()
