from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0029_marketing_loyalty"
down_revision = "0028_delivery_fee_fields"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "tenants" in inspector.get_table_names():
        if not _has_column(inspector, "tenants", "points_enabled"):
            op.add_column("tenants", sa.Column("points_enabled", sa.Boolean(), nullable=False, server_default="0"))
        if not _has_column(inspector, "tenants", "points_per_real"):
            op.add_column("tenants", sa.Column("points_per_real", sa.Numeric(10, 4), nullable=False, server_default="1"))
        if not _has_column(inspector, "tenants", "points_expiration_days"):
            op.add_column("tenants", sa.Column("points_expiration_days", sa.Integer(), nullable=True))

    if "coupons" in inspector.get_table_names():
        if _has_column(inspector, "coupons", "type") and not _has_column(inspector, "coupons", "discount_type"):
            op.alter_column("coupons", "type", new_column_name="discount_type")
        if _has_column(inspector, "coupons", "value") and not _has_column(inspector, "coupons", "discount_value"):
            op.alter_column("coupons", "value", new_column_name="discount_value")
        if _has_column(inspector, "coupons", "expires_at") and not _has_column(inspector, "coupons", "valid_until"):
            op.alter_column("coupons", "expires_at", new_column_name="valid_until")

    if "rewards" not in inspector.get_table_names():
        op.create_table(
            "rewards",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("points_required", sa.Integer(), nullable=False),
            sa.Column("discount_value", sa.Numeric(10, 2), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_rewards_tenant_id", "rewards", ["tenant_id"])

    if "customer_point_transactions" not in inspector.get_table_names():
        op.create_table(
            "customer_point_transactions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=False),
            sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=True),
            sa.Column("points_delta", sa.Integer(), nullable=False),
            sa.Column("reason", sa.String(length=64), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_customer_point_transactions_tenant_id", "customer_point_transactions", ["tenant_id"])
        op.create_index("ix_customer_point_transactions_customer_id", "customer_point_transactions", ["customer_id"])
        op.create_index("ix_customer_point_transactions_order_id", "customer_point_transactions", ["order_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "customer_point_transactions" in inspector.get_table_names():
        op.drop_index("ix_customer_point_transactions_order_id", table_name="customer_point_transactions")
        op.drop_index("ix_customer_point_transactions_customer_id", table_name="customer_point_transactions")
        op.drop_index("ix_customer_point_transactions_tenant_id", table_name="customer_point_transactions")
        op.drop_table("customer_point_transactions")

    if "rewards" in inspector.get_table_names():
        op.drop_index("ix_rewards_tenant_id", table_name="rewards")
        op.drop_table("rewards")

    if "coupons" in inspector.get_table_names():
        if _has_column(inspector, "coupons", "discount_type") and not _has_column(inspector, "coupons", "type"):
            op.alter_column("coupons", "discount_type", new_column_name="type")
        if _has_column(inspector, "coupons", "discount_value") and not _has_column(inspector, "coupons", "value"):
            op.alter_column("coupons", "discount_value", new_column_name="value")
        if _has_column(inspector, "coupons", "valid_until") and not _has_column(inspector, "coupons", "expires_at"):
            op.alter_column("coupons", "valid_until", new_column_name="expires_at")

    if "tenants" in inspector.get_table_names():
        if _has_column(inspector, "tenants", "points_expiration_days"):
            op.drop_column("tenants", "points_expiration_days")
        if _has_column(inspector, "tenants", "points_per_real"):
            op.drop_column("tenants", "points_per_real")
        if _has_column(inspector, "tenants", "points_enabled"):
            op.drop_column("tenants", "points_enabled")
