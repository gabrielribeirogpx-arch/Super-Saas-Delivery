from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "7f9c21ab3d4e"
down_revision = "0020_create_delivery_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "delivery_tracking",
        sa.Column("current_lat", sa.Float(), nullable=True)
    )
    op.add_column(
        "delivery_tracking",
        sa.Column("current_lng", sa.Float(), nullable=True)
    )
    op.add_column(
        "delivery_tracking",
        sa.Column("route_distance_meters", sa.Integer(), nullable=True)
    )
    op.add_column(
        "delivery_tracking",
        sa.Column("route_duration_seconds", sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("delivery_tracking", "route_duration_seconds")
    op.drop_column("delivery_tracking", "route_distance_meters")
    op.drop_column("delivery_tracking", "current_lng")
    op.drop_column("delivery_tracking", "current_lat")
