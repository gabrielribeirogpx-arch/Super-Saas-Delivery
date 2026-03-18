from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0020_create_delivery_tracking"
down_revision = "0019_delivery_user_status"
branch_labels = None
depends_on = None


def _has_index(inspector, table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "delivery_tracking" not in inspector.get_table_names():
        op.create_table(
            "delivery_tracking",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("order_id", sa.Integer(), nullable=False),
            sa.Column("delivery_user_id", sa.Integer(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("estimated_duration_seconds", sa.Integer(), nullable=False),
            sa.Column("expected_delivery_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["delivery_user_id"], ["admin_users.id"], ondelete="SET NULL"),
        )
    inspector = inspect(bind)
    if not _has_index(inspector, "delivery_tracking", "ix_delivery_tracking_order_id"):
        op.create_index("ix_delivery_tracking_order_id", "delivery_tracking", ["order_id"])
    if not _has_index(inspector, "delivery_tracking", "ix_delivery_tracking_delivery_user_id"):
        op.create_index("ix_delivery_tracking_delivery_user_id", "delivery_tracking", ["delivery_user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "delivery_tracking" in inspector.get_table_names():
        if _has_index(inspector, "delivery_tracking", "ix_delivery_tracking_delivery_user_id"):
            op.drop_index("ix_delivery_tracking_delivery_user_id", table_name="delivery_tracking")
        if _has_index(inspector, "delivery_tracking", "ix_delivery_tracking_order_id"):
            op.drop_index("ix_delivery_tracking_order_id", table_name="delivery_tracking")
        op.drop_table("delivery_tracking")
