from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0013_item_mods_col"
down_revision = "0012_item_modifiers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "order_items",
        sa.Column(
            "modifiers",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )

    op.execute("UPDATE order_items SET modifiers = '[]'::jsonb WHERE modifiers IS NULL")

    op.alter_column(
        "order_items",
        "modifiers",
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column("order_items", "modifiers")
