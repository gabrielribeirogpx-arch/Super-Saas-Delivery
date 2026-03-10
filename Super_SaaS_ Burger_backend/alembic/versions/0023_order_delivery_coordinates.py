from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0023_order_delivery_coordinates"
down_revision = "0022_delivery_fk_fix"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("delivery_lat", sa.Float(), nullable=True))
    op.add_column("orders", sa.Column("delivery_lng", sa.Float(), nullable=True))


    op.execute(
        """
        UPDATE orders
        SET delivery_lat = customer_lat,
            delivery_lng = customer_lng
        WHERE delivery_lat IS NULL
          AND delivery_lng IS NULL
          AND customer_lat IS NOT NULL
          AND customer_lng IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_column("orders", "delivery_lng")
    op.drop_column("orders", "delivery_lat")
