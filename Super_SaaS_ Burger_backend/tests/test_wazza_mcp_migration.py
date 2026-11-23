from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
import pytest
import sqlalchemy as sa

from app.models.tenant import Tenant


ROOT = Path(__file__).resolve().parents[1]
PREVIOUS_HEAD = "20261121_01_checkout_address"
HEAD = "20261123_03_wazza_confirmation"
TABLES = {"wazza_mcp_credentials", "wazza_mcp_audit_log", "wazza_order_drafts"}


@pytest.fixture(autouse=True)
def preserve_logging(monkeypatch):
    monkeypatch.setattr("logging.config.fileConfig", lambda *args, **kwargs: None)


def _config(url: str, output_buffer=None) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"), output_buffer=output_buffer)
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def test_wazza_mcp_migration_is_the_single_head():
    script = ScriptDirectory.from_config(_config("sqlite://"))
    assert script.get_heads() == [HEAD]


def test_wazza_mcp_migration_roundtrip_on_sqlite(tmp_path):
    url = f"sqlite:///{tmp_path / 'wazza.db'}"
    cfg = _config(url)
    engine = sa.create_engine(url)
    Tenant.__table__.create(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE orders (id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, UNIQUE (id, tenant_id))"
        )
    command.stamp(cfg, PREVIOUS_HEAD)
    command.upgrade(cfg, "20261123_02_wazza_order_drafts")
    with engine.begin() as connection:
        connection.execute(Tenant.__table__.insert().values(id=1, slug="legacy-draft-tenant"))
        connection.exec_driver_sql(
            "INSERT INTO wazza_order_drafts (public_id, tenant_id, owner_hash, status, items_json, "
            "mutation_keys_json, version, created_at, updated_at, expires_at) "
            "VALUES (?, 1, ?, 'active', '[]', '{}', 2, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
            ("a" * 32, "b" * 64),
        )
    command.upgrade(cfg, "head")
    with engine.connect() as connection:
        assert connection.exec_driver_sql(
            "SELECT status, version, confirmed_order_id FROM wazza_order_drafts"
        ).one() == ("active", 2, None)
    inspector = sa.inspect(engine)
    assert TABLES <= set(inspector.get_table_names())
    credential_columns = {column["name"] for column in inspector.get_columns("wazza_mcp_credentials")}
    assert {"tenant_id", "key_id", "token_hash", "scopes_json", "revoked_at"} <= credential_columns
    draft_columns = {column["name"] for column in inspector.get_columns("wazza_order_drafts")}
    assert {"public_id", "tenant_id", "owner_hash", "items_json", "fulfillment_json", "payment_json", "mutation_keys_json", "expires_at"} <= draft_columns
    command.downgrade(cfg, PREVIOUS_HEAD)
    assert not TABLES & set(sa.inspect(engine).get_table_names())
    engine.dispose()


def test_wazza_mcp_postgresql_sql_has_composite_tenant_constraint():
    output = StringIO()
    cfg = _config("postgresql+psycopg://unused:unused@localhost/unused", output)
    command.upgrade(cfg, f"{PREVIOUS_HEAD}:{HEAD}", sql=True)
    sql = output.getvalue()
    assert "CREATE TABLE wazza_mcp_credentials" in sql
    assert "CREATE TABLE wazza_mcp_audit_log" in sql
    assert "CREATE TABLE wazza_order_drafts" in sql
    assert "FOREIGN KEY(credential_id, tenant_id)" in sql
    assert "REFERENCES wazza_mcp_credentials (id, tenant_id)" in sql
    assert "FOREIGN KEY(confirmed_order_id, tenant_id) REFERENCES orders (id, tenant_id)" in sql
    assert "token_hash" in sql
