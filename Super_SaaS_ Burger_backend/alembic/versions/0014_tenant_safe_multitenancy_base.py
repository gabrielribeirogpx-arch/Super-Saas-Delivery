from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0014_tenant_safe_multitenancy_base"
down_revision = "0013_item_mods_col"
branch_labels = None
depends_on = None


def _columns_by_name(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    existing = _columns_by_name("tenants")

    if "name" not in existing:
        op.add_column(
            "tenants",
            sa.Column("name", sa.String(), nullable=False, server_default="Loja Padrão"),
        )
        op.alter_column("tenants", "name", server_default=None)

    if "is_active" not in existing:
        op.add_column(
            "tenants",
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        )
        op.alter_column("tenants", "is_active", server_default=None)

    if "created_at" not in existing:
        op.add_column(
            "tenants",
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.execute("UPDATE tenants SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
        op.alter_column("tenants", "created_at", nullable=False)


def downgrade() -> None:
    existing = _columns_by_name("tenants")

    if "created_at" in existing:
        op.drop_column("tenants", "created_at")
    if "is_active" in existing:
        op.drop_column("tenants", "is_active")
    if "name" in existing:
        op.drop_column("tenants", "name")
