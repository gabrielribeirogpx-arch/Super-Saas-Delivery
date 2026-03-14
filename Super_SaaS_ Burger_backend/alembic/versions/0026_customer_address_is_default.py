from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0026_customer_address_is_default"
down_revision = "0025_customer_account_fields"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "customer_addresses" in inspector.get_table_names() and not _has_column(inspector, "customer_addresses", "is_default"):
        op.add_column(
            "customer_addresses",
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "customer_addresses" in inspector.get_table_names() and _has_column(inspector, "customer_addresses", "is_default"):
        op.drop_column("customer_addresses", "is_default")
