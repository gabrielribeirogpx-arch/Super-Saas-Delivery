from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0018_public_tracking"
down_revision = "0017_delivery_logs"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _columns_by_name(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def _indexes_by_name(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    if not _table_exists("orders"):
        return

    existing_columns = _columns_by_name("orders")

    if "tracking_token" not in existing_columns:
        op.add_column("orders", sa.Column("tracking_token", sa.String(length=64), nullable=True))
    if "tracking_expires_at" not in existing_columns:
        op.add_column("orders", sa.Column("tracking_expires_at", sa.DateTime(timezone=True), nullable=True))
    if "polyline_encoded" not in existing_columns:
        op.add_column("orders", sa.Column("polyline_encoded", sa.Text(), nullable=True))
    if "route_distance_meters" not in existing_columns:
        op.add_column("orders", sa.Column("route_distance_meters", sa.Integer(), nullable=True))
    if "route_duration_seconds" not in existing_columns:
        op.add_column("orders", sa.Column("route_duration_seconds", sa.Integer(), nullable=True))
    if "eta_seconds" not in existing_columns:
        op.add_column("orders", sa.Column("eta_seconds", sa.Integer(), nullable=True))
    if "eta_at" not in existing_columns:
        op.add_column("orders", sa.Column("eta_at", sa.DateTime(timezone=True), nullable=True))
    if "delivery_last_lat" not in existing_columns:
        op.add_column("orders", sa.Column("delivery_last_lat", sa.Float(), nullable=True))
    if "delivery_last_lng" not in existing_columns:
        op.add_column("orders", sa.Column("delivery_last_lng", sa.Float(), nullable=True))
    if "delivery_last_location_at" not in existing_columns:
        op.add_column("orders", sa.Column("delivery_last_location_at", sa.DateTime(timezone=True), nullable=True))

    existing_indexes = _indexes_by_name("orders")
    if "ix_orders_tracking_token" not in existing_indexes:
        op.create_index("ix_orders_tracking_token", "orders", ["tracking_token"], unique=True)


def downgrade() -> None:
    if not _table_exists("orders"):
        return

    existing_columns = _columns_by_name("orders")
    existing_indexes = _indexes_by_name("orders")

    if "ix_orders_tracking_token" in existing_indexes:
        op.drop_index("ix_orders_tracking_token", table_name="orders")

    for column_name in [
        "delivery_last_location_at",
        "delivery_last_lng",
        "delivery_last_lat",
        "eta_at",
        "eta_seconds",
        "route_duration_seconds",
        "route_distance_meters",
        "polyline_encoded",
        "tracking_expires_at",
        "tracking_token",
    ]:
        if column_name in existing_columns:
            op.drop_column("orders", column_name)
