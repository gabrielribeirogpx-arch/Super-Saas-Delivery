from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_tenant_custom_domain"
down_revision = "0002_menu_public_slug"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("tenants") as batch:
        batch.add_column(sa.Column("custom_domain", sa.String(), nullable=True))

    op.create_index("ix_tenants_custom_domain", "tenants", ["custom_domain"], unique=True)
    op.execute("UPDATE tenants SET slug = 'tenant-1' WHERE id = 1 AND (slug IS NULL OR slug = '')")


def downgrade() -> None:
    op.drop_index("ix_tenants_custom_domain", table_name="tenants")

    with op.batch_alter_table("tenants") as batch:
        batch.drop_column("custom_domain")
