"""add order destination coordinates

Revision ID: 0030_order_destination_coordinates
Revises: 0029_marketing_loyalty
Create Date: 2025-02-15 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0030_order_destination_coordinates"
down_revision = "0029_marketing_loyalty"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col["name"] for col in inspector.get_columns("orders")]

    if "destination_lat" not in columns:
        op.add_column("orders", sa.Column("destination_lat", sa.Float(), nullable=True))

    if "destination_lng" not in columns:
        op.add_column("orders", sa.Column("destination_lng", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "destination_lng")
    op.drop_column("orders", "destination_lat")
