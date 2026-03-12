from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0024_order_daily_number"
down_revision = "0023_order_delivery_coordinates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("daily_order_number", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "daily_order_number")
