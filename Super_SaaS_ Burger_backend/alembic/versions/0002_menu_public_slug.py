from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0002_menu_public_slug"
down_revision = "0001_create_schema"
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
        if not _has_column(inspector, "tenants", "slug"):
            with op.batch_alter_table("tenants") as batch:
                batch.add_column(sa.Column("slug", sa.String(), nullable=True))

        inspector = inspect(bind)
        if not _has_index(inspector, "tenants", "ix_tenants_slug"):
            op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)

        op.execute("UPDATE tenants SET slug = 'tenant-' || id WHERE slug IS NULL")

        with op.batch_alter_table("tenants") as batch:
            batch.alter_column("slug", nullable=False)

    if inspector.has_table("menu_categories"):
        if _has_column(inspector, "menu_categories", "position") and not _has_column(inspector, "menu_categories", "sort_order"):
            with op.batch_alter_table("menu_categories") as batch:
                batch.alter_column(
                    "position",
                    new_column_name="sort_order",
                    existing_type=sa.Integer(),
                    nullable=False,
                )

    if inspector.has_table("menu_items"):
        if not _has_column(inspector, "menu_items", "description"):
            with op.batch_alter_table("menu_items") as batch:
                batch.add_column(sa.Column("description", sa.Text(), nullable=True))
        inspector = inspect(bind)
        if not _has_column(inspector, "menu_items", "image_url"):
            with op.batch_alter_table("menu_items") as batch:
                batch.add_column(sa.Column("image_url", sa.String(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if inspector.has_table("menu_items"):
        if _has_column(inspector, "menu_items", "image_url"):
            with op.batch_alter_table("menu_items") as batch:
                batch.drop_column("image_url")
        inspector = inspect(bind)
        if _has_column(inspector, "menu_items", "description"):
            with op.batch_alter_table("menu_items") as batch:
                batch.drop_column("description")

    if inspector.has_table("menu_categories") and _has_column(inspector, "menu_categories", "sort_order") and not _has_column(inspector, "menu_categories", "position"):
        with op.batch_alter_table("menu_categories") as batch:
            batch.alter_column(
                "sort_order",
                new_column_name="position",
                existing_type=sa.Integer(),
                nullable=False,
            )

    if inspector.has_table("tenants"):
        if _has_index(inspector, "tenants", "ix_tenants_slug"):
            op.drop_index("ix_tenants_slug", table_name="tenants")
        inspector = inspect(bind)
        if _has_column(inspector, "tenants", "slug"):
            with op.batch_alter_table("tenants") as batch:
                batch.drop_column("slug")
