"""customer phone otp auth

Revision ID: 20260716_customer_phone_otp
Revises: 20260710_restore_tenants_created_at_default
Create Date: 2026-07-16
"""
from alembic import op
import sqlalchemy as sa

revision = "20260716_customer_phone_otp"
down_revision = "20260710_tenant_created_default"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("customers") as batch:
        batch.add_column(sa.Column("phone_normalized", sa.String(length=32), nullable=True))
        batch.add_column(sa.Column("phone_verified_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_customers_phone_normalized", "customers", ["phone_normalized"])
    op.create_unique_constraint("ux_customers_tenant_phone_normalized", "customers", ["tenant_id", "phone_normalized"])
    op.create_table(
        "customer_otps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("phone_normalized", sa.String(length=32), nullable=False),
        sa.Column("code_hash", sa.String(length=128), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_customer_otps_tenant_id", "customer_otps", ["tenant_id"])
    op.create_index("ix_customer_otps_phone_normalized", "customer_otps", ["phone_normalized"])

def downgrade():
    op.drop_index("ix_customer_otps_phone_normalized", table_name="customer_otps")
    op.drop_index("ix_customer_otps_tenant_id", table_name="customer_otps")
    op.drop_table("customer_otps")
    op.drop_constraint("ux_customers_tenant_phone_normalized", "customers", type_="unique")
    op.drop_index("ix_customers_phone_normalized", table_name="customers")
    with op.batch_alter_table("customers") as batch:
        batch.drop_column("updated_at")
        batch.drop_column("is_active")
        batch.drop_column("phone_verified_at")
        batch.drop_column("phone_normalized")
