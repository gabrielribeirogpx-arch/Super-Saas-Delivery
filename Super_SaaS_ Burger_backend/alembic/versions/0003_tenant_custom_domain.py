from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0003_tenant_custom_domain"
down_revision = "0002_menu_public_slug"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _has_index(inspector, table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if inspector.has_table("tenants"):
        if not _has_column(inspector, "tenants", "custom_domain"):
            with op.batch_alter_table("tenants") as batch:
                batch.add_column(sa.Column("custom_domain", sa.String(), nullable=True))

        inspector = inspect(bind)
        if not _has_index(inspector, "tenants", "ix_tenants_custom_domain"):
            op.create_index("ix_tenants_custom_domain", "tenants", ["custom_domain"], unique=True)

        op.execute("UPDATE tenants SET slug = 'tenant-1' WHERE id = 1 AND (slug IS NULL OR slug = '')")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if inspector.has_table("tenants"):
        if _has_index(inspector, "tenants", "ix_tenants_custom_domain"):
            op.drop_index("ix_tenants_custom_domain", table_name="tenants")
        inspector = inspect(bind)
        if _has_column(inspector, "tenants", "custom_domain"):
            with op.batch_alter_table("tenants") as batch:
                batch.drop_column("custom_domain")
