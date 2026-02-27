from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0008_product_config"
down_revision = "0007_estimated_prep_time"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "modifier_groups" in inspector.get_table_names():
        if not _has_column("modifier_groups", "product_id"):
            op.add_column("modifier_groups", sa.Column("product_id", sa.Integer(), nullable=True))
            op.create_foreign_key(
                "fk_modifier_groups_product_id_menu_items",
                "modifier_groups",
                "menu_items",
                ["product_id"],
                ["id"],
            )
        if not _has_column("modifier_groups", "description"):
            op.add_column("modifier_groups", sa.Column("description", sa.Text(), nullable=True))
        if not _has_column("modifier_groups", "required"):
            op.add_column("modifier_groups", sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.false()))
        if not _has_column("modifier_groups", "min_selection"):
            op.add_column("modifier_groups", sa.Column("min_selection", sa.Integer(), nullable=False, server_default="0"))
        if not _has_column("modifier_groups", "max_selection"):
            op.add_column("modifier_groups", sa.Column("max_selection", sa.Integer(), nullable=False, server_default="1"))
        if not _has_column("modifier_groups", "order_index"):
            op.add_column("modifier_groups", sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"))

        try:
            op.create_index("ix_modifier_groups_product_id", "modifier_groups", ["product_id"], unique=False)
        except Exception:
            pass

    if "modifier_options" not in inspector.get_table_names():
        op.create_table(
            "modifier_options",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("group_id", sa.Integer(), sa.ForeignKey("modifier_groups.id"), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("price_delta", sa.Numeric(10, 2), nullable=False, server_default="0"),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        )
        op.create_index("ix_modifier_options_group_id", "modifier_options", ["group_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "modifier_options" in inspector.get_table_names():
        op.drop_index("ix_modifier_options_group_id", table_name="modifier_options")
        op.drop_table("modifier_options")

    if "modifier_groups" in inspector.get_table_names():
        for col in ["order_index", "max_selection", "min_selection", "required", "description", "product_id"]:
            if _has_column("modifier_groups", col):
                if col == "product_id":
                    try:
                        op.drop_index("ix_modifier_groups_product_id", table_name="modifier_groups")
                    except Exception:
                        pass
                    try:
                        op.drop_constraint("fk_modifier_groups_product_id_menu_items", "modifier_groups", type_="foreignkey")
                    except Exception:
                        pass
                op.drop_column("modifier_groups", col)
