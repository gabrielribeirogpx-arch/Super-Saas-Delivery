from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0021_order_customer_coordinates"
down_revision = "7f9c21ab3d4e"
branch_labels = None
depends_on = None


def _columns_by_name(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    existing = _columns_by_name("orders")
    if "customer_lat" not in existing:
        op.add_column("orders", sa.Column("customer_lat", sa.Float(), nullable=True))
    if "customer_lng" not in existing:
        op.add_column("orders", sa.Column("customer_lng", sa.Float(), nullable=True))


def downgrade() -> None:
    existing = _columns_by_name("orders")
    if "customer_lng" in existing:
        op.drop_column("orders", "customer_lng")
    if "customer_lat" in existing:
        op.drop_column("orders", "customer_lat")
