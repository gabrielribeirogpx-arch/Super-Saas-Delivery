from __future__ import annotations

from alembic import op

revision = "0004_normalize_tenant_domains"
down_revision = "0003_tenant_custom_domain"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE tenants SET slug = lower(slug) WHERE slug IS NOT NULL")
    op.execute(
        "UPDATE tenants SET custom_domain = lower(custom_domain) WHERE custom_domain IS NOT NULL"
    )


def downgrade() -> None:
    pass
