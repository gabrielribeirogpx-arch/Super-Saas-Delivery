from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_store_theme"
down_revision = "0005_tenant_public"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "store_themes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("primary_color", sa.String(length=32), nullable=True),
        sa.Column("secondary_color", sa.String(length=32), nullable=True),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("cover_url", sa.Text(), nullable=True),
        sa.Column("slogan", sa.String(length=255), nullable=True),
        sa.Column("show_logo_on_cover", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("tenant_id", name="ux_store_themes_tenant_id"),
    )
    op.create_index("ix_store_themes_tenant_id", "store_themes", ["tenant_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_store_themes_tenant_id", table_name="store_themes")
    op.drop_table("store_themes")
