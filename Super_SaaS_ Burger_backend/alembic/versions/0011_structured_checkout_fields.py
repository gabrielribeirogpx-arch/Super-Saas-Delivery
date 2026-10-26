from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0011_structured_checkout_fields"
down_revision = "0010_coupons_system"
branch_labels = None
depends_on = None


ORDER_TYPE_ENUM = sa.Enum("delivery", "pickup", "table", name="order_type_enum", native_enum=False)


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "orders" not in inspector.get_table_names():
        return

    ORDER_TYPE_ENUM.create(bind, checkfirst=True)

    if not _has_column(inspector, "orders", "order_type"):
        op.add_column(
            "orders",
            sa.Column("order_type", ORDER_TYPE_ENUM, nullable=False, server_default="delivery"),
        )

    for column in [
        sa.Column("street", sa.String(length=255), nullable=True),
        sa.Column("number", sa.String(length=50), nullable=True),
        sa.Column("complement", sa.String(length=255), nullable=True),
        sa.Column("neighborhood", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=255), nullable=True),
        sa.Column("reference", sa.String(length=255), nullable=True),
        sa.Column("table_number", sa.String(length=50), nullable=True),
        sa.Column("command_number", sa.String(length=50), nullable=True),
        sa.Column("change_for", sa.Numeric(10, 2), nullable=True),
        sa.Column("channel", sa.String(length=50), nullable=True),
    ]:
        if not _has_column(inspector, "orders", column.name):
            op.add_column("orders", column)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "orders" not in inspector.get_table_names():
        return

    for column_name in [
        "channel",
        "change_for",
        "command_number",
        "table_number",
        "reference",
        "city",
        "neighborhood",
        "complement",
        "number",
        "street",
        "order_type",
    ]:
        if _has_column(inspector, "orders", column_name):
            op.drop_column("orders", column_name)

    ORDER_TYPE_ENUM.drop(bind, checkfirst=True)
