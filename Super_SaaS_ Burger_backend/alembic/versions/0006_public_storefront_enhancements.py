from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_public_storefront_enhancements"
down_revision = "0005_tenant_public"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenant_public_settings", sa.Column("is_open", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("tenant_public_settings", sa.Column("estimated_time_min", sa.Integer(), nullable=True))
    op.add_column("tenant_public_settings", sa.Column("banner_blur_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("tenant_public_settings", sa.Column("banner_blur_intensity", sa.Integer(), nullable=True, server_default="6"))
    op.add_column("tenant_public_settings", sa.Column("banner_overlay_opacity", sa.Float(), nullable=True, server_default="0.55"))


def downgrade() -> None:
    op.drop_column("tenant_public_settings", "banner_overlay_opacity")
    op.drop_column("tenant_public_settings", "banner_blur_intensity")
    op.drop_column("tenant_public_settings", "banner_blur_enabled")
    op.drop_column("tenant_public_settings", "estimated_time_min")
    op.drop_column("tenant_public_settings", "is_open")
