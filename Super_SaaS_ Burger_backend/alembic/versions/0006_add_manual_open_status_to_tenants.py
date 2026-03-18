from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0006_manual_open_status"
down_revision = "0005_tenant_public"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table("tenants") and not _has_column(inspector, "tenants", "manual_open_status"):
        op.add_column("tenants", sa.Column("manual_open_status", sa.Boolean(), nullable=False, server_default=sa.true()))
        op.alter_column("tenants", "manual_open_status", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if inspector.has_table("tenants") and _has_column(inspector, "tenants", "manual_open_status"):
        op.drop_column("tenants", "manual_open_status")
