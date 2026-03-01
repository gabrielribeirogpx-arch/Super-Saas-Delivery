from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0015_delivery_timestamps"
down_revision = "0014_tenant_base"
branch_labels = None
depends_on = None


def _columns_by_name(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    existing = _columns_by_name("orders")

    if "ready_at" not in existing:
        op.add_column("orders", sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True))

    if "start_delivery_at" not in existing:
        op.add_column("orders", sa.Column("start_delivery_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    existing = _columns_by_name("orders")

    if "start_delivery_at" in existing:
        op.drop_column("orders", "start_delivery_at")

    if "ready_at" in existing:
        op.drop_column("orders", "ready_at")
