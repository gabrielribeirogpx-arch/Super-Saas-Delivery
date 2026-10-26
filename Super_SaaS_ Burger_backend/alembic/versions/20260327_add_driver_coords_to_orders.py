from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260327_driver_coords"
down_revision = "38bc7e536b23"
branch_labels = None
depends_on = None


def _columns_by_name(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    existing = _columns_by_name("orders")
    if "driver_lat" not in existing:
        op.add_column("orders", sa.Column("driver_lat", sa.Float(), nullable=True))
    if "driver_lng" not in existing:
        op.add_column("orders", sa.Column("driver_lng", sa.Float(), nullable=True))


def downgrade() -> None:
    existing = _columns_by_name("orders")
    if "driver_lng" in existing:
        op.drop_column("orders", "driver_lng")
    if "driver_lat" in existing:
        op.drop_column("orders", "driver_lat")
