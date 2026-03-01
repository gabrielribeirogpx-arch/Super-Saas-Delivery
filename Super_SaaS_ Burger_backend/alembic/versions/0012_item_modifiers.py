from __future__ import annotations

from alembic import op
from sqlalchemy import inspect


revision = "0012_item_modifiers"
down_revision = "0011_structured_checkout_fields"
branch_labels = None
depends_on = None


def _has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if not _has_table(inspector, "order_items"):
        return
    if not _has_column(inspector, "order_items", "modifiers"):
        return

    op.execute("UPDATE order_items SET modifiers = '[]' WHERE modifiers IS NULL")


def downgrade() -> None:
    return
