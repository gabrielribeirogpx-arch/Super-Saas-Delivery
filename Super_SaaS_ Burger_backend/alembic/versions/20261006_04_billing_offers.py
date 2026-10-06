"""Create explicit external offer mappings."""
from alembic import op
import sqlalchemy as sa

revision = "20261006_04_billing_offers"
down_revision = "20261006_03_subscriptions"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "billing_offer_mappings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("environment", sa.String(20), nullable=False),
        sa.Column("provider_account_id", sa.String(255), nullable=False),
        sa.Column("external_product_id", sa.String(255), nullable=False),
        sa.Column("external_offer_id", sa.String(255), nullable=False),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("plans.id"), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("provider", "environment", "provider_account_id", "external_product_id", "external_offer_id", name="uq_billing_offer_external"),
        sa.CheckConstraint("environment IN ('sandbox', 'production')", name="ck_billing_offer_environment"),
        sa.CheckConstraint("length(provider) > 0 AND length(provider_account_id) > 0 AND length(external_product_id) > 0 AND length(external_offer_id) > 0", name="ck_billing_offer_identity"),
    )


def downgrade():
    op.drop_table("billing_offer_mappings")
