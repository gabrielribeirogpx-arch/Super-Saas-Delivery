"""add_route_geometry

Revision ID: 03c4fd22a767
Revises: 0021_order_customer_coordinates
Create Date: 2026-03-04 09:15:46.497354

"""

from alembic import op
import sqlalchemy as sa

revision = "03c4fd22a767"
down_revision = "0021_order_customer_coordinates"
branch_labels = None
depends_on = None


def _columns_by_name(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade():
    if "route_geometry" not in _columns_by_name("delivery_tracking"):
        op.add_column("delivery_tracking", sa.Column("route_geometry", sa.JSON(), nullable=True))


def downgrade():
    if "route_geometry" in _columns_by_name("delivery_tracking"):
        op.drop_column("delivery_tracking", "route_geometry")
