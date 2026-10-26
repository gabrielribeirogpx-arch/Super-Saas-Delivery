"""Create opaque tenant checkout intents; no external checkout."""
from alembic import op
import sqlalchemy as sa

revision = "20261006_05_billing_intents"
down_revision = "20261006_04_billing_offers"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "billing_checkout_intents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_token", sa.String(64), nullable=False),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("plans.id"), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("provider_account_id", sa.String(255), nullable=False),
        sa.Column("environment", sa.String(20), nullable=False),
        sa.Column("status", sa.Enum("pending", "completed", "expired", "canceled", native_enum=False, create_constraint=True, name="billing_intent_status"), nullable=False, server_default="pending"),
        sa.Column("external_checkout_id", sa.String(255), nullable=True),
        sa.Column("external_customer_id", sa.String(255), nullable=True),
        sa.Column("external_subscription_id", sa.String(255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("public_token", name="uq_billing_intent_token"),
        sa.UniqueConstraint("provider", "provider_account_id", "environment", "external_checkout_id", name="uq_billing_intent_external_checkout"),
        sa.UniqueConstraint("id", "tenant_id", name="uq_billing_intent_id_tenant"),
        sa.CheckConstraint("environment IN ('sandbox', 'production')", name="ck_billing_intent_environment"),
        sa.CheckConstraint("length(public_token) >= 43 AND length(provider) > 0 AND length(provider_account_id) > 0", name="ck_billing_intent_identity"),
        sa.CheckConstraint("status != 'completed' OR completed_at IS NOT NULL", name="ck_billing_intent_completed"),
    )
    op.create_index("ix_billing_checkout_intents_tenant_id", "billing_checkout_intents", ["tenant_id"])


def downgrade():
    op.drop_index("ix_billing_checkout_intents_tenant_id", table_name="billing_checkout_intents")
    op.drop_table("billing_checkout_intents")
