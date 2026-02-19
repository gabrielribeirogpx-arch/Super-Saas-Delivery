"""add store theme fields

Revision ID: 0006_store_theme_fields
Revises: 0005_create_tenant_public_settings
Create Date: 2026-02-19
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0006_store_theme_fields"
down_revision = "0005_create_tenant_public_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenant_public_settings", sa.Column("accent_color", sa.String(length=255), nullable=True))
    op.add_column("tenant_public_settings", sa.Column("background_color", sa.String(length=255), nullable=True))
    op.add_column("tenant_public_settings", sa.Column("surface_color", sa.String(length=255), nullable=True))
    op.add_column("tenant_public_settings", sa.Column("button_radius", sa.Integer(), nullable=True))
    op.add_column("tenant_public_settings", sa.Column("card_radius", sa.Integer(), nullable=True))
    op.add_column("tenant_public_settings", sa.Column("hero_overlay_opacity", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("tenant_public_settings", "hero_overlay_opacity")
    op.drop_column("tenant_public_settings", "card_radius")
    op.drop_column("tenant_public_settings", "button_radius")
    op.drop_column("tenant_public_settings", "surface_color")
    op.drop_column("tenant_public_settings", "background_color")
    op.drop_column("tenant_public_settings", "accent_color")
