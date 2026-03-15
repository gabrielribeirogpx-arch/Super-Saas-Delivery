from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0028_delivery_fee_fields"
down_revision = "0027_create_customer_points"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "tenants" in inspector.get_table_names() and not _has_column(inspector, "tenants", "delivery_fee"):
        op.add_column(
            "tenants",
            sa.Column("delivery_fee", sa.Numeric(10, 2), nullable=False, server_default="0"),
        )

    if "orders" in inspector.get_table_names():
        if not _has_column(inspector, "orders", "subtotal"):
            op.add_column(
                "orders",
                sa.Column("subtotal", sa.Numeric(10, 2), nullable=False, server_default="0"),
            )
        if not _has_column(inspector, "orders", "delivery_fee"):
            op.add_column(
                "orders",
                sa.Column("delivery_fee", sa.Numeric(10, 2), nullable=False, server_default="0"),
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "orders" in inspector.get_table_names():
        if _has_column(inspector, "orders", "delivery_fee"):
            op.drop_column("orders", "delivery_fee")
        if _has_column(inspector, "orders", "subtotal"):
            op.drop_column("orders", "subtotal")

    if "tenants" in inspector.get_table_names() and _has_column(inspector, "tenants", "delivery_fee"):
        op.drop_column("tenants", "delivery_fee")
