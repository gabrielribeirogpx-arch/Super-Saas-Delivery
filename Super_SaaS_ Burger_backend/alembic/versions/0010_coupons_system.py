from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0010_coupons_system"
down_revision = "0009_customers_base"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _has_index(inspector, table_name: str, index_name: str) -> bool:
    return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))


def _has_unique_constraint(inspector, table_name: str, name: str) -> bool:
    return any(constraint["name"] == name for constraint in inspector.get_unique_constraints(table_name))


def _has_fk(inspector, table_name: str, name: str) -> bool:
    return any(fk["name"] == name for fk in inspector.get_foreign_keys(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "coupons" not in inspector.get_table_names():
        op.create_table(
            "coupons",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("code", sa.String(length=64), nullable=False),
            sa.Column("type", sa.String(length=20), nullable=False),
            sa.Column("value", sa.Numeric(10, 2), nullable=False),
            sa.Column("min_order_value", sa.Numeric(10, 2), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("max_uses", sa.Integer(), nullable=True),
            sa.Column("uses_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("vip_only", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    inspector = inspect(bind)
    if not _has_index(inspector, "coupons", "ix_coupons_tenant_id"):
        op.create_index("ix_coupons_tenant_id", "coupons", ["tenant_id"], unique=False)
    if not _has_unique_constraint(inspector, "coupons", "uq_coupons_tenant_code"):
        op.create_unique_constraint("uq_coupons_tenant_code", "coupons", ["tenant_id", "code"])

    inspector = inspect(bind)
    if "coupon_redemptions" not in inspector.get_table_names():
        op.create_table(
            "coupon_redemptions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("coupon_id", sa.Integer(), sa.ForeignKey("coupons.id"), nullable=False),
            sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=True),
            sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    inspector = inspect(bind)
    if not _has_index(inspector, "coupon_redemptions", "ix_coupon_redemptions_coupon_id"):
        op.create_index("ix_coupon_redemptions_coupon_id", "coupon_redemptions", ["coupon_id"], unique=False)
    if not _has_index(inspector, "coupon_redemptions", "ix_coupon_redemptions_customer_id"):
        op.create_index("ix_coupon_redemptions_customer_id", "coupon_redemptions", ["customer_id"], unique=False)
    if not _has_index(inspector, "coupon_redemptions", "ix_coupon_redemptions_order_id"):
        op.create_index("ix_coupon_redemptions_order_id", "coupon_redemptions", ["order_id"], unique=False)

    inspector = inspect(bind)
    if "orders" in inspector.get_table_names():
        if not _has_column(inspector, "orders", "coupon_id"):
            op.add_column("orders", sa.Column("coupon_id", sa.Integer(), nullable=True))
            op.create_foreign_key("fk_orders_coupon_id_coupons", "orders", "coupons", ["coupon_id"], ["id"])
        if not _has_column(inspector, "orders", "discount_amount"):
            op.add_column("orders", sa.Column("discount_amount", sa.Numeric(10, 2), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "orders" in inspector.get_table_names():
        if _has_fk(inspector, "orders", "fk_orders_coupon_id_coupons"):
            op.drop_constraint("fk_orders_coupon_id_coupons", "orders", type_="foreignkey")
        inspector = inspect(bind)
        if _has_column(inspector, "orders", "discount_amount"):
            op.drop_column("orders", "discount_amount")
        if _has_column(inspector, "orders", "coupon_id"):
            op.drop_column("orders", "coupon_id")

    inspector = inspect(bind)
    if "coupon_redemptions" in inspector.get_table_names():
        for index_name in [
            "ix_coupon_redemptions_order_id",
            "ix_coupon_redemptions_customer_id",
            "ix_coupon_redemptions_coupon_id",
        ]:
            if _has_index(inspector, "coupon_redemptions", index_name):
                op.drop_index(index_name, table_name="coupon_redemptions")
        op.drop_table("coupon_redemptions")

    inspector = inspect(bind)
    if "coupons" in inspector.get_table_names():
        if _has_unique_constraint(inspector, "coupons", "uq_coupons_tenant_code"):
            op.drop_constraint("uq_coupons_tenant_code", "coupons", type_="unique")
        if _has_index(inspector, "coupons", "ix_coupons_tenant_id"):
            op.drop_index("ix_coupons_tenant_id", table_name="coupons")
        op.drop_table("coupons")
