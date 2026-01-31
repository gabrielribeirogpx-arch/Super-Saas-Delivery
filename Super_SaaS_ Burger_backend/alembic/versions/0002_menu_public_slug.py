from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_menu_public_slug"
down_revision = "0001_create_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("tenants") as batch:
        batch.add_column(sa.Column("slug", sa.String(), nullable=True))

    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)
    op.execute("UPDATE tenants SET slug = 'tenant-' || id WHERE slug IS NULL")

    with op.batch_alter_table("tenants") as batch:
        batch.alter_column("slug", nullable=False)

    with op.batch_alter_table("menu_categories") as batch:
        batch.alter_column(
            "position",
            new_column_name="sort_order",
            existing_type=sa.Integer(),
            nullable=False,
        )

    with op.batch_alter_table("menu_items") as batch:
        batch.add_column(sa.Column("description", sa.Text(), nullable=True))
        batch.add_column(sa.Column("image_url", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("menu_items") as batch:
        batch.drop_column("image_url")
        batch.drop_column("description")

    with op.batch_alter_table("menu_categories") as batch:
        batch.alter_column(
            "sort_order",
            new_column_name="position",
            existing_type=sa.Integer(),
            nullable=False,
        )

    op.drop_index("ix_tenants_slug", table_name="tenants")

    with op.batch_alter_table("tenants") as batch:
        batch.drop_column("slug")
