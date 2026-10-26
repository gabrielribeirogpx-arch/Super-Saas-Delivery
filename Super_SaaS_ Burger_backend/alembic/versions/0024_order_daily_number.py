from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0024_order_daily_number"
down_revision = "0023_order_delivery_coordinates"
branch_labels = None
depends_on = None


def _columns_by_name(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    if "daily_order_number" not in _columns_by_name("orders"):
        op.add_column("orders", sa.Column("daily_order_number", sa.Integer(), nullable=True))


def downgrade() -> None:
    if "daily_order_number" in _columns_by_name("orders"):
        op.drop_column("orders", "daily_order_number")
