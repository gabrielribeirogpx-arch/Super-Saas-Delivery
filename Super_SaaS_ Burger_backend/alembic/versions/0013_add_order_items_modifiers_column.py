from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect


revision = "0013_add_order_items_modifiers_column"
down_revision = "0012_item_modifiers"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "order_items" not in inspector.get_table_names():
        return

    if not _has_column(inspector, "order_items", "modifiers"):
        op.add_column(
            "order_items",
            sa.Column(
                "modifiers",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
        )

    op.execute("UPDATE order_items SET modifiers = '[]'::jsonb WHERE modifiers IS NULL")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "order_items" not in inspector.get_table_names():
        return

    if _has_column(inspector, "order_items", "modifiers"):
        op.drop_column("order_items", "modifiers")
