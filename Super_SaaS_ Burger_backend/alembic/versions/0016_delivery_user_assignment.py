from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0016_delivery_user_assignment"
down_revision = "0015_delivery_timestamps"
branch_labels = None
depends_on = None


def _columns_by_name(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def _indexes_by_name(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _foreign_keys_by_name(table_name: str) -> set[str | None]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {fk.get("name") for fk in inspector.get_foreign_keys(table_name)}


def upgrade() -> None:
    existing_columns = _columns_by_name("orders")
    if "assigned_delivery_user_id" not in existing_columns:
        op.add_column("orders", sa.Column("assigned_delivery_user_id", sa.Integer(), nullable=True))

    existing_indexes = _indexes_by_name("orders")
    if "ix_orders_assigned_delivery_user_id" not in existing_indexes:
        op.create_index("ix_orders_assigned_delivery_user_id", "orders", ["assigned_delivery_user_id"], unique=False)

    bind = op.get_bind()
    existing_fks = _foreign_keys_by_name("orders")
    if bind.dialect.name != "sqlite" and "fk_orders_assigned_delivery_user_id_users" not in existing_fks:
        op.create_foreign_key(
            "fk_orders_assigned_delivery_user_id_users",
            "orders",
            "users",
            ["assigned_delivery_user_id"],
            ["id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    existing_fks = _foreign_keys_by_name("orders")
    if bind.dialect.name != "sqlite" and "fk_orders_assigned_delivery_user_id_users" in existing_fks:
        op.drop_constraint("fk_orders_assigned_delivery_user_id_users", "orders", type_="foreignkey")

    existing_indexes = _indexes_by_name("orders")
    if "ix_orders_assigned_delivery_user_id" in existing_indexes:
        op.drop_index("ix_orders_assigned_delivery_user_id", table_name="orders")

    existing_columns = _columns_by_name("orders")
    if "assigned_delivery_user_id" in existing_columns:
        op.drop_column("orders", "assigned_delivery_user_id")
