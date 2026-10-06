from io import StringIO
from pathlib import Path

import pytest

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from app.models.plan import Plan
from app.models.plan_entitlement import PlanEntitlement
from app.models.subscription import Subscription
from app.models.tenant import Tenant
from app.services.plan_seed import seed_plans

ROOT = Path(__file__).resolve().parents[1]
PREVIOUS = "20260716_customer_phone_otp"
HEAD = "20261006_03_subscriptions"


@pytest.fixture(autouse=True)
def preserve_application_logging(monkeypatch):
    # Alembic's fileConfig disables application loggers and replaces pytest handlers.
    # The migration tests run in-process, so keep logging isolated from other tests.
    monkeypatch.setattr("logging.config.fileConfig", lambda *args, **kwargs: None)


def config(url, output_buffer=None):
    cfg = Config(str(ROOT / "alembic.ini"), output_buffer=output_buffer)
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def test_migrations_upgrade_downgrade_preserve_operational_tenant(tmp_path):
    url = f"sqlite:///{tmp_path / 'migration.db'}"
    engine = create_engine(url)
    # Simulate a database already at the previous production revision.
    Tenant.__table__.create(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO tenants (id, name, business_name, is_active, slug, manual_open_status) VALUES (1, 'Legacy', 'Legacy', 1, 'legacy', 1)"))
        conn.execute(text("CREATE TABLE operational_sentinel (id INTEGER PRIMARY KEY, value TEXT)"))
        conn.execute(text("INSERT INTO operational_sentinel VALUES (1, 'unchanged')"))
    before = inspect(engine).get_columns("tenants")
    cfg = config(url)
    assert ScriptDirectory.from_config(cfg).get_heads() == [HEAD]
    command.stamp(cfg, PREVIOUS)
    command.upgrade(cfg, HEAD)
    inspector = inspect(engine)
    for model in (Plan, PlanEntitlement, Subscription):
        assert {c["name"] for c in inspector.get_columns(model.__tablename__)} == {c.name for c in model.__table__.columns}
    assert inspector.get_unique_constraints("subscriptions")[0]["column_names"] == ["tenant_id"]
    assert {tuple(fk["constrained_columns"]): fk["referred_table"] for fk in inspector.get_foreign_keys("subscriptions")} == {("tenant_id",): "tenants", ("plan_id",): "plans"}
    with Session(engine) as db:
        seed_plans(db)
        db.commit()
        seed_plans(db)
        db.commit()
        assert db.query(Plan).count() == 3
        assert db.query(PlanEntitlement).count() == 30
        assert db.query(Subscription).count() == 0
    command.downgrade(cfg, PREVIOUS)
    assert "plans" not in inspect(engine).get_table_names()
    assert "plan_entitlements" not in inspect(engine).get_table_names()
    assert "subscriptions" not in inspect(engine).get_table_names()
    assert [(c["name"], str(c["type"]), c["nullable"], c["default"]) for c in inspect(engine).get_columns("tenants")] == [(c["name"], str(c["type"]), c["nullable"], c["default"]) for c in before]
    with engine.connect() as conn:
        assert conn.execute(text("SELECT slug FROM tenants WHERE id=1")).scalar_one() == "legacy"
        assert conn.execute(text("SELECT value FROM operational_sentinel")).scalar_one() == "unchanged"
    command.upgrade(cfg, HEAD)
    assert "subscriptions" in inspect(engine).get_table_names()
    engine.dispose()


def test_new_migrations_generate_postgresql_sql_without_operational_ddl():
    output = StringIO()
    cfg = config("postgresql+psycopg://unused:unused@localhost/unused", output)
    command.upgrade(cfg, f"{PREVIOUS}:{HEAD}", sql=True)
    sql = output.getvalue()
    for table in ("plans", "plan_entitlements", "subscriptions"):
        assert f"CREATE TABLE {table}" in sql
    assert "FOREIGN KEY(tenant_id) REFERENCES tenants (id)" in sql
    assert "CONSTRAINT subscription_status CHECK" in sql
    assert "CREATE TYPE" not in sql
    assert "ALTER TABLE tenants" not in sql
    assert "DROP TABLE" not in sql
