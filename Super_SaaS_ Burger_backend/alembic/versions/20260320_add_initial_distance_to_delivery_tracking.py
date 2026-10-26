"""add initial distance meters to delivery tracking

Revision ID: 20260320_initial_distance
Revises: 03c4fd22a767
Create Date: 2026-03-20 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20260320_initial_distance"
down_revision = "03c4fd22a767"
branch_labels = None
depends_on = None


def _columns_by_name(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    existing = _columns_by_name("delivery_tracking")
    if "initial_distance_meters" not in existing:
        op.add_column("delivery_tracking", sa.Column("initial_distance_meters", sa.Integer(), nullable=True))


def downgrade() -> None:
    existing = _columns_by_name("delivery_tracking")
    if "initial_distance_meters" in existing:
        op.drop_column("delivery_tracking", "initial_distance_meters")
