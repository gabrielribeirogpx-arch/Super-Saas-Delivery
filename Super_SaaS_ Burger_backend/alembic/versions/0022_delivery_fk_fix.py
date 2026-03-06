from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0022_delivery_fk_fix"
down_revision = "03c4fd22a767"
branch_labels = None
depends_on = None


FK_NAME = "fk_orders_assigned_delivery_user_id_users"
NEW_FK_NAME = "fk_orders_assigned_delivery_user_id_admin_users"


def _foreign_keys(table_name: str) -> list[dict]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.get_foreign_keys(table_name)


def _has_fk(table_name: str, fk_name: str) -> bool:
    return any((fk.get("name") or "") == fk_name for fk in _foreign_keys(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        with op.batch_alter_table("orders") as batch_op:
            batch_op.drop_constraint(FK_NAME, type_="foreignkey")
            batch_op.create_foreign_key(NEW_FK_NAME, "admin_users", ["assigned_delivery_user_id"], ["id"])
        return

    if _has_fk("orders", FK_NAME):
        op.drop_constraint(FK_NAME, "orders", type_="foreignkey")
    if not _has_fk("orders", NEW_FK_NAME):
        op.create_foreign_key(
            NEW_FK_NAME,
            "orders",
            "admin_users",
            ["assigned_delivery_user_id"],
            ["id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        with op.batch_alter_table("orders") as batch_op:
            batch_op.drop_constraint(NEW_FK_NAME, type_="foreignkey")
            batch_op.create_foreign_key(FK_NAME, "users", ["assigned_delivery_user_id"], ["id"])
        return

    if _has_fk("orders", NEW_FK_NAME):
        op.drop_constraint(NEW_FK_NAME, "orders", type_="foreignkey")
    if not _has_fk("orders", FK_NAME):
        op.create_foreign_key(
            FK_NAME,
            "orders",
            "users",
            ["assigned_delivery_user_id"],
            ["id"],
        )
