from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision = "0013_item_mods_col"
down_revision = "0012_item_modifiers"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("order_items") or _has_column(inspector, "order_items", "modifiers"):
        return

    column_type = postgresql.JSONB(astext_type=sa.Text()) if bind.dialect.name != "sqlite" else sa.JSON()
    op.add_column("order_items", sa.Column("modifiers", column_type, nullable=True))
    if bind.dialect.name == "postgresql":
        op.execute("UPDATE order_items SET modifiers = '[]'::jsonb WHERE modifiers IS NULL")
    else:
        op.execute("UPDATE order_items SET modifiers = '[]' WHERE modifiers IS NULL")
    op.alter_column("order_items", "modifiers", nullable=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table("order_items") and _has_column(inspector, "order_items", "modifiers"):
        op.drop_column("order_items", "modifiers")
