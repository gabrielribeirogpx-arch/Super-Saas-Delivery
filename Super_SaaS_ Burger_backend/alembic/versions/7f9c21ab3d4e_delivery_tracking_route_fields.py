from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "7f9c21ab3d4e"
down_revision = "0020_create_delivery_tracking"
branch_labels = None
depends_on = None


def _columns_by_name(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    existing = _columns_by_name("delivery_tracking")
    if "current_lat" not in existing:
        op.add_column("delivery_tracking", sa.Column("current_lat", sa.Float(), nullable=True))
    if "current_lng" not in existing:
        op.add_column("delivery_tracking", sa.Column("current_lng", sa.Float(), nullable=True))
    if "route_distance_meters" not in existing:
        op.add_column("delivery_tracking", sa.Column("route_distance_meters", sa.Integer(), nullable=True))
    if "route_duration_seconds" not in existing:
        op.add_column("delivery_tracking", sa.Column("route_duration_seconds", sa.Integer(), nullable=True))


def downgrade() -> None:
    existing = _columns_by_name("delivery_tracking")
    if "route_duration_seconds" in existing:
        op.drop_column("delivery_tracking", "route_duration_seconds")
    if "route_distance_meters" in existing:
        op.drop_column("delivery_tracking", "route_distance_meters")
    if "current_lng" in existing:
        op.drop_column("delivery_tracking", "current_lng")
    if "current_lat" in existing:
        op.drop_column("delivery_tracking", "current_lat")
