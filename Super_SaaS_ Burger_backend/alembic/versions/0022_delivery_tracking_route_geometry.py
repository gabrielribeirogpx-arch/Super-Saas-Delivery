from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0022_delivery_tracking_route_geometry"
down_revision = "0021_order_customer_coordinates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "delivery_tracking",
        sa.Column("route_geometry", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("delivery_tracking", "route_geometry")
