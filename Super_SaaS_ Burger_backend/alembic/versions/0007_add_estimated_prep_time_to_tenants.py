from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0007_estimated_prep_time"
down_revision = "0006_manual_open_status"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table("tenants") and not _has_column(inspector, "tenants", "estimated_prep_time"):
        op.add_column("tenants", sa.Column("estimated_prep_time", sa.String(length=50), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table("tenants") and _has_column(inspector, "tenants", "estimated_prep_time"):
        op.drop_column("tenants", "estimated_prep_time")
