from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_widen_tenant_public_settings_columns"
down_revision = "0005_create_tenant_public_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("tenant_public_settings") as batch_op:
        batch_op.alter_column(
            "cover_image_url",
            existing_type=sa.String(length=32),
            type_=sa.Text(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "cover_video_url",
            existing_type=sa.String(length=32),
            type_=sa.Text(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "logo_url",
            existing_type=sa.String(length=32),
            type_=sa.Text(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "theme",
            existing_type=sa.String(length=32),
            type_=sa.String(length=255),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "primary_color",
            existing_type=sa.String(length=32),
            type_=sa.String(length=255),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("tenant_public_settings") as batch_op:
        batch_op.alter_column(
            "primary_color",
            existing_type=sa.String(length=255),
            type_=sa.String(length=32),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "theme",
            existing_type=sa.String(length=255),
            type_=sa.String(length=32),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "logo_url",
            existing_type=sa.Text(),
            type_=sa.String(length=32),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "cover_video_url",
            existing_type=sa.Text(),
            type_=sa.String(length=32),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "cover_image_url",
            existing_type=sa.Text(),
            type_=sa.String(length=32),
            existing_nullable=True,
        )
