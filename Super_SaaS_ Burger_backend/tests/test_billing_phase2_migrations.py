from io import StringIO
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models.admin_audit_log import AdminAuditLog
from app.models.admin_user import AdminUser
from app.models.billing_checkout_intent import BillingCheckoutIntent
from app.models.billing_event import BillingEvent
from app.models.billing_offer_mapping import BillingOfferMapping
from app.models.subscription import Subscription
from app.models.tenant import Tenant
from app.services.plan_seed import seed_plans

ROOT = Path(__file__).resolve().parents[1]
PHASE1 = "20261006_03_subscriptions"
HEAD = "20261006_07_billing_audit"
PHASE2_TABLES = {"billing_offer_mappings", "billing_checkout_intents", "billing_events"}
VERIFICATION_COLUMNS = {"verification_status", "verification_attempts", "verification_next_at", "verification_lease_until",
                        "verification_lease_token", "verification_error_code", "verified_at"}


@pytest.fixture(autouse=True)
def preserve_logging(monkeypatch):
    monkeypatch.setattr("logging.config.fileConfig", lambda *args, **kwargs: None)


def config(url, output_buffer=None):
    cfg = Config(str(ROOT / "alembic.ini"), output_buffer=output_buffer)
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


@pytest.fixture
def phase1_db(tmp_path):
    url = f"sqlite:///{tmp_path / 'phase1.db'}"
    engine = sa.create_engine(url)
    Tenant.__table__.create(engine)
    AdminUser.__table__.create(engine)
    old_metadata = sa.MetaData()
    audit = sa.Table("admin_audit_log", old_metadata,
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
        sa.Column("user_id", sa.Integer(), nullable=False, index=True),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("meta_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True))
    audit.create(engine)
    cfg = config(url)
    command.stamp(cfg, "20260716_customer_phone_otp")
    command.upgrade(cfg, PHASE1)
    with Session(engine) as db, db.begin():
        db.add(Tenant(id=1, slug="legacy"))
        db.flush()
        db.add(AdminUser(id=1, tenant_id=1, email="legacy@example.test", name="Legacy", password_hash="hash"))
        seed_plans(db)
        db.execute(sa.text("INSERT INTO subscriptions (id, tenant_id, plan_id, status) VALUES (1, 1, 1, 'active')"))
        db.execute(audit.insert().values(id=1, tenant_id=1, user_id=1, action="legacy.action", entity_type="subscription", entity_id=1, meta_json='{"preserved":true}'))
    yield engine, cfg
    engine.dispose()


def test_phase2_migrations_roundtrip_preserves_phase1_data_and_matches_models(phase1_db):
    engine, cfg = phase1_db
    tenant_columns = sa.inspect(engine).get_columns("tenants")
    script = ScriptDirectory.from_config(cfg)
    assert script.get_heads() == ["20261007_02_billing_review"]
    command.upgrade(cfg, HEAD)
    inspector = sa.inspect(engine)
    assert PHASE2_TABLES <= set(inspector.get_table_names())
    for model in (BillingOfferMapping, BillingCheckoutIntent, BillingEvent, Subscription, AdminAuditLog):
        expected = {c.name for c in model.__table__.columns}
        if model is BillingEvent:
            expected -= VERIFICATION_COLUMNS
        assert {c["name"] for c in inspector.get_columns(model.__tablename__)} == expected
    tables = PHASE2_TABLES | {"subscriptions", "admin_audit_log"}
    def include_object(obj, name, kind, reflected, compare_to):
        table = obj if kind == "table" else getattr(obj, "table", None)
        if table is not None and table.name == "billing_events":
            if kind == "column" and name in VERIFICATION_COLUMNS:
                return False
            if kind == "index" and name == "ix_billing_events_verification_status":
                return False
        return table is None or table.name in tables
    with engine.connect() as conn:
        differences = compare_metadata(MigrationContext.configure(conn, opts={"include_object": include_object}), Base.metadata)
        assert differences == []
        assert conn.execute(sa.text("SELECT version FROM subscriptions WHERE id=1")).scalar_one() == 1
        assert conn.execute(sa.text("SELECT actor_type FROM admin_audit_log WHERE id=1")).scalar_one() == "user"
        assert conn.execute(sa.text("SELECT user_id FROM admin_audit_log WHERE id=1")).scalar_one() == 1
        assert conn.execute(sa.text("PRAGMA foreign_key_check")).all() == []
    command.downgrade(cfg, PHASE1)
    inspector = sa.inspect(engine)
    assert not PHASE2_TABLES & set(inspector.get_table_names())
    assert "version" not in {c["name"] for c in inspector.get_columns("subscriptions")}
    assert "actor_type" not in {c["name"] for c in inspector.get_columns("admin_audit_log")}
    assert next(c for c in inspector.get_columns("admin_audit_log") if c["name"] == "user_id")["nullable"] is False
    assert [(c["name"], str(c["type"]), c["nullable"], c["default"]) for c in inspector.get_columns("tenants")] == [(c["name"], str(c["type"]), c["nullable"], c["default"]) for c in tenant_columns]
    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT status, tenant_id, plan_id FROM subscriptions WHERE id=1")).one() == ("active", 1, 1)
        assert conn.execute(sa.text("SELECT action, user_id, meta_json FROM admin_audit_log WHERE id=1")).one() == ("legacy.action", 1, '{"preserved":true}')
    command.upgrade(cfg, HEAD)
    assert PHASE2_TABLES <= set(sa.inspect(engine).get_table_names())


def test_downgrade_refuses_to_erase_or_falsify_automatic_audit(phase1_db):
    engine, cfg = phase1_db
    command.upgrade(cfg, HEAD)
    with engine.begin() as conn:
        conn.execute(sa.text("INSERT INTO admin_audit_log (tenant_id, user_id, actor_type, action) VALUES (1, NULL, 'system', 'subscription.created')"))
    with pytest.raises(RuntimeError, match="Archive automatic audit records"):
        command.downgrade(cfg, PHASE1)
    assert PHASE2_TABLES <= set(sa.inspect(engine).get_table_names())
    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT COUNT(*) FROM admin_audit_log WHERE actor_type='system' AND user_id IS NULL")).scalar_one() == 1
        assert conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one() == HEAD


def test_phase2_migrated_composite_fks_enforce_tenant_isolation(phase1_db):
    engine, cfg = phase1_db
    command.upgrade(cfg, HEAD)
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        conn.commit()
        with conn.begin():
            conn.execute(sa.text("INSERT INTO tenants (id, name, business_name, is_active, slug, manual_open_status) VALUES (2, 'Other', 'Other', 1, 'other', 1)"))
        with pytest.raises(sa.exc.IntegrityError), conn.begin():
            conn.execute(sa.text("INSERT INTO billing_events (provider, environment, provider_account_id, provider_event_id, event_type, payload_hash, raw_payload, tenant_id, subscription_id) VALUES ('kiwify', 'sandbox', 'account-1', 'event-1', 'paid', :hash, '{}', 2, 1)"), {"hash": "a" * 64})
        with conn.begin():
            conn.execute(sa.text("INSERT INTO billing_events (provider, environment, provider_account_id, provider_event_id, event_type, payload_hash, raw_payload, tenant_id, subscription_id) VALUES ('kiwify', 'sandbox', 'account-1', 'event-2', 'paid', :hash, '{}', 1, 1)"), {"hash": "b" * 64})


def test_phase2_postgresql_upgrade_and_downgrade_sql():
    output = StringIO()
    cfg = config("postgresql+psycopg://unused:unused@localhost/unused", output)
    command.upgrade(cfg, f"{PHASE1}:{HEAD}", sql=True)
    sql = output.getvalue()
    for table in PHASE2_TABLES:
        assert f"CREATE TABLE {table}" in sql
    assert "uq_billing_event_identity" in sql
    assert "FOREIGN KEY(subscription_id, tenant_id) REFERENCES subscriptions (id, tenant_id)" in sql
    assert "ALTER TABLE admin_audit_log ALTER COLUMN user_id DROP NOT NULL" in sql
    assert "CREATE TYPE" not in sql
    output = StringIO()
    cfg = config("postgresql+psycopg://unused:unused@localhost/unused", output)
    command.downgrade(cfg, f"{HEAD}:{PHASE1}", sql=True)
    sql = output.getvalue()
    assert "Archive automatic audit records before downgrade" in sql
    assert "ALTER COLUMN user_id SET NOT NULL" in sql
    for table in PHASE2_TABLES:
        assert f"DROP TABLE {table}" in sql
