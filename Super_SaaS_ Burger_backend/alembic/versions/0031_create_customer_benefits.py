from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0031_create_customer_benefits"
down_revision = "594f9e82b5d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "customer_benefits" not in inspector.get_table_names():
        op.create_table(
            "customer_benefits",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=False),
            sa.Column("benefit_type", sa.String(length=40), nullable=False),
            sa.Column("title", sa.String(length=120), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("benefit_value", sa.Numeric(10, 2), nullable=True),
            sa.Column("coupon_code", sa.String(length=80), nullable=True),
            sa.Column("active", sa.Boolean(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_customer_benefits_tenant_id", "customer_benefits", ["tenant_id"])
        op.create_index("ix_customer_benefits_customer_id", "customer_benefits", ["customer_id"])
        op.create_index("ix_customer_benefits_benefit_type", "customer_benefits", ["benefit_type"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "customer_benefits" in inspector.get_table_names():
        op.drop_index("ix_customer_benefits_benefit_type", table_name="customer_benefits")
        op.drop_index("ix_customer_benefits_customer_id", table_name="customer_benefits")
        op.drop_index("ix_customer_benefits_tenant_id", table_name="customer_benefits")
        op.drop_table("customer_benefits")
