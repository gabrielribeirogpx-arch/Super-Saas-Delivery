"""verified customer email accounts with signup contact details

Revision ID: 20261120_01_customer_account
Revises: 20261119_02_customer_email
"""
from alembic import op
import sqlalchemy as sa

revision = "20261120_01_customer_account"
down_revision = "20261119_02_customer_email"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("customer_email_otps", sa.Column("pending_name", sa.String(length=120), nullable=True))
    op.add_column("customer_email_otps", sa.Column("pending_phone", sa.String(length=32), nullable=True))
    op.create_table(
        "customer_email_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("email_normalized", sa.String(length=254), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("phone_normalized", sa.String(length=32), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "email_normalized", name="uq_customer_email_account_tenant_email"),
    )
    op.create_index("ix_customer_email_accounts_tenant_id", "customer_email_accounts", ["tenant_id"])


def downgrade():
    op.drop_index("ix_customer_email_accounts_tenant_id", table_name="customer_email_accounts")
    op.drop_table("customer_email_accounts")
    op.drop_column("customer_email_otps", "pending_phone")
    op.drop_column("customer_email_otps", "pending_name")
