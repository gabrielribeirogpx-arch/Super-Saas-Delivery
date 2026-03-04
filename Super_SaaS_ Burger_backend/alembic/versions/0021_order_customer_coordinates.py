from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0021_order_customer_coordinates"
down_revision = "7f9c21ab3d4e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("customer_lat", sa.Float(), nullable=True)
    )
    op.add_column(
        "orders",
        sa.Column("customer_lng", sa.Float(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("orders", "customer_lng")
    op.drop_column("orders", "customer_lat")
