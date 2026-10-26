from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0023_order_delivery_coordinates"
down_revision = "0022_delivery_fk_fix"
branch_labels = None
depends_on = None


def _columns_by_name(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    existing = _columns_by_name("orders")
    if "delivery_lat" not in existing:
        op.add_column("orders", sa.Column("delivery_lat", sa.Float(), nullable=True))
    if "delivery_lng" not in existing:
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
    existing = _columns_by_name("orders")
    if "delivery_lng" in existing:
        op.drop_column("orders", "delivery_lng")
    if "delivery_lat" in existing:
        op.drop_column("orders", "delivery_lat")
