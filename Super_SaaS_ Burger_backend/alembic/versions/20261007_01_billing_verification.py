"""Separate verification from domain processing; shared outbound rate budget."""
from alembic import context, op
import sqlalchemy as sa

revision = "20261007_01_billing_verification"
down_revision = "20261006_07_billing_audit"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("billing_events") as batch:
        batch.add_column(sa.Column("verification_status", sa.String(13), nullable=False, server_default="pending"))
        batch.add_column(sa.Column("verification_attempts", sa.Integer(), nullable=False, server_default="0"))
        for name in ("verification_next_at", "verification_lease_until", "verified_at"):
            batch.add_column(sa.Column(name, sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("verification_lease_token", sa.String(64), nullable=True))
        batch.add_column(sa.Column("verification_error_code", sa.String(100), nullable=True))
        batch.create_check_constraint("billing_verification_status", "verification_status IN ('pending','verified','rejected','retrying','manual_review')")
        batch.create_check_constraint("ck_billing_verification_attempts", "verification_attempts >= 0")
        batch.create_check_constraint("ck_billing_verified_at", "verification_status != 'verified' OR verified_at IS NOT NULL")
        batch.create_index("ix_billing_events_verification_status", ["verification_status"])
    op.create_table("billing_provider_budgets",
        sa.Column("provider", sa.String(50), primary_key=True),
        sa.Column("next_request_at", sa.DateTime(timezone=True), nullable=False))


def downgrade():
    # Do not discard the distinction between untrusted and authoritative receipts.
    bind = op.get_bind()
    if context.is_offline_mode():
        if bind.dialect.name != "postgresql":
            raise RuntimeError("Offline downgrade requires PostgreSQL or an online verification preflight")
        op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM billing_events WHERE provider='kiwify' AND schema_version=2) THEN RAISE EXCEPTION 'Archive Kiwify verification receipts before downgrade'; END IF; END $$;")
    elif bind.execute(sa.text("SELECT count(*) FROM billing_events WHERE provider='kiwify' AND schema_version=2")).scalar():
        raise RuntimeError("Archive Kiwify verification receipts before downgrade")
    op.drop_table("billing_provider_budgets")
    with op.batch_alter_table("billing_events") as batch:
        batch.drop_index("ix_billing_events_verification_status")
        for name in ("billing_verification_status", "ck_billing_verification_attempts", "ck_billing_verified_at"):
            batch.drop_constraint(name, type_="check")
        for name in ("verification_status", "verification_attempts", "verification_next_at", "verification_lease_until",
                     "verification_lease_token", "verification_error_code", "verified_at"):
            batch.drop_column(name)
