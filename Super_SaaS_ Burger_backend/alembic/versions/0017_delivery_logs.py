from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0017_delivery_logs"
down_revision = "0016_delivery_user_assignment"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _indexes_by_name(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    if not _table_exists("delivery_logs"):
        op.create_table(
            "delivery_logs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("order_id", sa.Integer(), nullable=False),
            sa.Column("delivery_user_id", sa.Integer(), nullable=False),
            sa.Column("event_type", sa.String(), nullable=False),
            sa.Column("latitude", sa.Float(), nullable=True),
            sa.Column("longitude", sa.Float(), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    existing_indexes = _indexes_by_name("delivery_logs")
    if "idx_delivery_logs_order" not in existing_indexes:
        op.create_index("idx_delivery_logs_order", "delivery_logs", ["order_id"], unique=False)
    if "idx_delivery_logs_user" not in existing_indexes:
        op.create_index("idx_delivery_logs_user", "delivery_logs", ["delivery_user_id"], unique=False)
    if "idx_delivery_logs_created" not in existing_indexes:
        op.create_index("idx_delivery_logs_created", "delivery_logs", ["created_at"], unique=False)
    if "idx_delivery_logs_event" not in existing_indexes:
        op.create_index("idx_delivery_logs_event", "delivery_logs", ["event_type"], unique=False)


def downgrade() -> None:
    if _table_exists("delivery_logs"):
        op.drop_index("idx_delivery_logs_event", table_name="delivery_logs")
        op.drop_index("idx_delivery_logs_created", table_name="delivery_logs")
        op.drop_index("idx_delivery_logs_user", table_name="delivery_logs")
        op.drop_index("idx_delivery_logs_order", table_name="delivery_logs")
        op.drop_table("delivery_logs")
