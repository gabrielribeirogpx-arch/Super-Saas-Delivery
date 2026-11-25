"""Index per-store order chronology."""

import sqlalchemy as sa
from alembic import op

revision = "20261125_01_order_history_index"
down_revision = "20261124_01_management_push"
branch_labels = None
depends_on = None

INDEX = "ix_orders_tenant_created_id"


def upgrade():
    if op.get_context().dialect.name == "postgresql":
        # PostgreSQL can leave an invalid index if a build is interrupted.
        # Remove it before retrying, while preserving a completed index.
        with op.get_context().autocommit_block():
            if not op.get_context().as_sql:
                invalid = op.get_bind().scalar(sa.text("""
                    SELECT NOT indisvalid FROM pg_index
                    WHERE indexrelid = to_regclass(:index)
                """), {"index": INDEX})
                if invalid:
                    op.drop_index(INDEX, table_name="orders", postgresql_concurrently=True)
            op.create_index(INDEX, "orders", ["tenant_id", "created_at", "id"],
                            if_not_exists=True, postgresql_concurrently=True)
    else:
        op.create_index(INDEX, "orders", ["tenant_id", "created_at", "id"])


def downgrade():
    if op.get_context().dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.drop_index(INDEX, table_name="orders", postgresql_concurrently=True, if_exists=True)
    else:
        op.drop_index(INDEX, table_name="orders")
