from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0027_create_customer_points"
down_revision = "0026_customer_address_is_default"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "customer_points" not in inspector.get_table_names():
        op.create_table(
            "customer_points",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=False),
            sa.Column("available_points", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("lifetime_points", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_customer_points_tenant_id", "customer_points", ["tenant_id"])
        op.create_index("ix_customer_points_customer_id", "customer_points", ["customer_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "customer_points" in inspector.get_table_names():
        op.drop_index("ix_customer_points_customer_id", table_name="customer_points")
        op.drop_index("ix_customer_points_tenant_id", table_name="customer_points")
        op.drop_table("customer_points")
