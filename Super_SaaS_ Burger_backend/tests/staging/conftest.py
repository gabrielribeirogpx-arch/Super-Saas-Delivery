"""Opt-in real PostgreSQL validation in owned, disposable schemas only."""
import logging
import os
import secrets
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
import app.models
from app.models.tenant import Tenant
from app.models.admin_user import AdminUser
from app.services.plan_seed import seed_plans

BASELINE = "20260716_customer_phone_otp"
HEAD = "20261007_02_billing_review"
BILLING_TABLES = {"plans", "plan_entitlements", "subscriptions", "billing_offer_mappings",
    "billing_checkout_intents", "billing_events", "billing_provider_budgets", "billing_manual_reviews"}
ROOT = Path(__file__).resolve().parents[2]


def migration_config(url):
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


@pytest.fixture
def history_pg(monkeypatch):
    """Empty owned schema: no metadata.create_all and no Alembic stamp."""
    value = os.environ.get("FOMIZERO_PHASE4_DATABASE_URL")
    if not value:
        pytest.skip("Opt-in PostgreSQL staging URL not configured")
    if os.environ.get("FOMIZERO_PHASE4_CONFIRM_STAGING") != "yes":
        pytest.fail("Explicit staging confirmation required; production is forbidden")
    url = sa.engine.make_url(value)
    if url.get_backend_name() != "postgresql" or url.host not in {"localhost", "127.0.0.1", "::1"}:
        pytest.fail("Loopback PostgreSQL only")
    schema = "fomizero_phase4_history_" + uuid4().hex
    admin = sa.create_engine(url, hide_parameters=True)
    with admin.begin() as conn:
        conn.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    scoped = url.update_query_dict({"options": "-csearch_path=" + schema})
    engine = sa.create_engine(scoped, hide_parameters=True)
    monkeypatch.setattr("logging.config.fileConfig", lambda *a, **kw: None)
    try:
        yield engine, migration_config(scoped.render_as_string(hide_password=False))
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def pg(monkeypatch):
    value = os.environ.get("FOMIZERO_PHASE4_DATABASE_URL")
    if not value:
        pytest.skip("Opt-in PostgreSQL staging URL not configured")
    if os.environ.get("FOMIZERO_PHASE4_CONFIRM_STAGING") != "yes":
        pytest.fail("Explicit staging confirmation required; production is forbidden")
    url = sa.engine.make_url(value)
    if url.get_backend_name() != "postgresql":
        pytest.fail("Real PostgreSQL is required")
    if url.host not in {"localhost", "127.0.0.1", "::1"}:
        pytest.fail("Phase 4 currently permits loopback PostgreSQL only; no production/staging remote connection")
    # Do not connect through DATABASE_URL or fall back to a production connection.
    schema = "fomizero_phase4_" + uuid4().hex
    admin = sa.create_engine(url, hide_parameters=True)
    with admin.begin() as conn:
        conn.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    scoped = url.update_query_dict({"options": "-csearch_path=" + schema})
    engine = sa.create_engine(scoped, hide_parameters=True)
    cfg = migration_config(scoped.render_as_string(hide_password=False))
    monkeypatch.setattr("logging.config.fileConfig", lambda *a, **kw: None)
    monkeypatch.setattr("app.services.admin_auth.ADMIN_SESSION_SECRET", secrets.token_urlsafe(32))
    try:
        # Explicit synthetic pre-billing baseline, NOT an empty-history upgrade.
        # The full-history check is separate and must never be reported as passing
        # merely because this scoped billing fixture succeeds.
        tables = [t for t in Base.metadata.sorted_tables if t.name not in BILLING_TABLES | {"admin_audit_log"}]
        Base.metadata.create_all(engine, tables=tables)
        meta = sa.MetaData()
        sa.Table("admin_audit_log", meta,
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
            sa.Column("user_id", sa.Integer(), nullable=False, index=True),
            sa.Column("action", sa.String(), nullable=False), sa.Column("entity_type", sa.String()),
            sa.Column("entity_id", sa.Integer()), sa.Column("meta_json", sa.Text()),
            sa.Column("created_at", sa.DateTime())).create(engine)
        command.stamp(cfg, BASELINE)
        command.upgrade(cfg, HEAD)
        sessions = sessionmaker(bind=engine)
        with sessions() as db, db.begin():
            db.add_all([Tenant(slug="phase4-a"), Tenant(slug="phase4-b")])
            db.flush()
            db.add_all([AdminUser(tenant_id=1, role="owner", email="owner-a@example.com", name="Staging A", password_hash="not-a-login-secret"),
                        AdminUser(tenant_id=2, role="admin", email="admin-b@example.com", name="Staging B", password_hash="not-a-login-secret"),
                        AdminUser(tenant_id=1, role="operator", email="operator-a@example.com", name="Staging operator", password_hash="not-a-login-secret")])
            seed_plans(db)
        yield engine, cfg, sessions
    finally:
        engine.dispose()
        # Only the randomly named schema created by THIS fixture is removed.
        with admin.begin() as conn:
            conn.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
