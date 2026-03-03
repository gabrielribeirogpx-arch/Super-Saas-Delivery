from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0019_delivery_user_status"
down_revision = "0018_order_public_tracking"
branch_labels = None
depends_on = None



def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()



def _column_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}



def upgrade() -> None:
    if not _table_exists("admin_users"):
        return

    columns = _column_names("admin_users")
    if "status" in columns:
        return

    op.add_column(
        "admin_users",
        sa.Column("status", sa.String(), nullable=False, server_default="OFFLINE"),
    )



def downgrade() -> None:
    if not _table_exists("admin_users"):
        return

    columns = _column_names("admin_users")
    if "status" not in columns:
        return

    op.drop_column("admin_users", "status")
