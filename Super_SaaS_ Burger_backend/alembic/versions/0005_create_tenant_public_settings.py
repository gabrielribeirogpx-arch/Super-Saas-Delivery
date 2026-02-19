from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_tenant_public"
down_revision = "0004_normalize_tenant_domains"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_public_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("cover_image_url", sa.Text(), nullable=True),
        sa.Column("cover_video_url", sa.Text(), nullable=True),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("theme", sa.String(255), nullable=True),
        sa.Column("primary_color", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("tenant_id", name="ux_tenant_public_settings_tenant_id"),
    )
    op.create_index(
        "ix_tenant_public_settings_tenant_id",
        "tenant_public_settings",
        ["tenant_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_tenant_public_settings_tenant_id", table_name="tenant_public_settings")
    op.drop_table("tenant_public_settings")
