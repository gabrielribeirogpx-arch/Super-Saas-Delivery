"""customer email codes and per-order email ownership

Revision ID: 20261119_02_customer_email
Revises: 20261119_01_owner_email
"""

from alembic import op
import sqlalchemy as sa


revision = "20261119_02_customer_email"
down_revision = "20261119_01_owner_email"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("orders", sa.Column("customer_email", sa.String(length=254), nullable=True))
    op.create_index("ix_orders_tenant_customer_email", "orders", ["tenant_id", "customer_email"])
    op.create_table(
        "customer_email_otps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("email_normalized", sa.String(length=254), nullable=False),
        sa.Column("code_hash", sa.String(length=128), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_customer_email_otps_tenant_id", "customer_email_otps", ["tenant_id"])
    op.create_index("ix_customer_email_otps_email_normalized", "customer_email_otps", ["email_normalized"])


def downgrade():
    op.drop_index("ix_customer_email_otps_email_normalized", table_name="customer_email_otps")
    op.drop_index("ix_customer_email_otps_tenant_id", table_name="customer_email_otps")
    op.drop_table("customer_email_otps")
    op.drop_index("ix_orders_tenant_customer_email", table_name="orders")
    op.drop_column("orders", "customer_email")
