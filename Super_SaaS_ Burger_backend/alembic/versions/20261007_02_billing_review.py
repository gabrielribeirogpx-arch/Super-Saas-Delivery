"""Sanitized official evidence and attributed human billing review decisions."""
from alembic import context, op
import sqlalchemy as sa

revision = "20261007_02_billing_review"
down_revision = "20261007_01_billing_verification"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("billing_manual_reviews",
        sa.Column("billing_event_id", sa.Integer(), sa.ForeignKey("billing_events.id"), primary_key=True),
        sa.Column("sale_id", sa.String(255)), sa.Column("product_id", sa.String(255)),
        sa.Column("external_subscription_id", sa.String(255)), sa.Column("external_offer_id", sa.String(255)),
        sa.Column("sale_status", sa.String(30)), sa.Column("sale_checked_at", sa.DateTime(timezone=True)),
        sa.Column("period_start", sa.DateTime(timezone=True)), sa.Column("period_end", sa.DateTime(timezone=True)),
        sa.Column("period_source", sa.String(50)), sa.Column("decision", sa.String(20)),
        sa.Column("decided_by", sa.Integer(), sa.ForeignKey("admin_users.id")),
        sa.Column("decided_at", sa.DateTime(timezone=True)), sa.Column("rejection_reason", sa.String(50)),
        sa.CheckConstraint("decision IS NULL OR decision IN ('approved','binding_approved','rejected')", name="ck_billing_review_decision"),
        sa.CheckConstraint("decision IS NULL OR (decided_at IS NOT NULL AND decided_by IS NOT NULL)", name="ck_billing_review_actor"),
        sa.CheckConstraint("(period_start IS NULL AND period_end IS NULL) OR (period_start IS NOT NULL AND period_end IS NOT NULL AND period_end > period_start)", name="ck_billing_review_period"))


def downgrade():
    if context.is_offline_mode():
        if op.get_bind().dialect.name != "postgresql":
            raise RuntimeError("Offline downgrade requires PostgreSQL")
        op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM billing_manual_reviews) THEN RAISE EXCEPTION 'Archive billing manual reviews before downgrade'; END IF; END $$;")
    elif op.get_bind().execute(sa.text("SELECT count(*) FROM billing_manual_reviews")).scalar():
        raise RuntimeError("Archive billing manual reviews before downgrade")
    op.drop_table("billing_manual_reviews")
