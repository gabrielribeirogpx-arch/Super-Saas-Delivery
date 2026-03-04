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


def upgrade():
    op.add_column(
        "delivery_tracking",
        sa.Column(
            "route_geometry",
            sa.JSON(),
            nullable=True
        )
    )


def downgrade():
    op.drop_column("delivery_tracking", "route_geometry")
