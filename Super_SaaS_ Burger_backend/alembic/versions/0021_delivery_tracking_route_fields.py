from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0021_delivery_tracking_route_fields"
down_revision = "0020_create_delivery_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("delivery_tracking", sa.Column("current_lat", sa.Float(), nullable=True))
    op.add_column("delivery_tracking", sa.Column("current_lng", sa.Float(), nullable=True))
    op.add_column("delivery_tracking", sa.Column("route_distance_meters", sa.Integer(), nullable=True))
    op.add_column("delivery_tracking", sa.Column("route_duration_seconds", sa.Integer(), nullable=True))
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_delivery_tracking_order_id ON delivery_tracking(order_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_delivery_tracking_order_id")
    op.drop_column("delivery_tracking", "route_duration_seconds")
    op.drop_column("delivery_tracking", "route_distance_meters")
    op.drop_column("delivery_tracking", "current_lng")
    op.drop_column("delivery_tracking", "current_lat")
