from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0020_create_delivery_tracking"
down_revision = "0019_delivery_user_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
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
    op.create_index("ix_delivery_tracking_order_id", "delivery_tracking", ["order_id"])
    op.create_index("ix_delivery_tracking_delivery_user_id", "delivery_tracking", ["delivery_user_id"])


def downgrade() -> None:
    op.drop_index("ix_delivery_tracking_delivery_user_id", table_name="delivery_tracking")
    op.drop_index("ix_delivery_tracking_order_id", table_name="delivery_tracking")
    op.drop_table("delivery_tracking")
