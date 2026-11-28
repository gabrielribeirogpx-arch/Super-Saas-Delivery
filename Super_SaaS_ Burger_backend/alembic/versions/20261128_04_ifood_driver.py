"""Store assignments for iFood merchant deliveries."""

import sqlalchemy as sa
from alembic import op

revision = "20261128_04_ifood_driver"
down_revision = "20261128_03_ifood_dispatch"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ifood_driver_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("ifood_orders.order_id"), nullable=False, unique=True),
        sa.Column("assigned_driver_id", sa.Integer(), sa.ForeignKey("admin_users.id")),
        sa.Column("destination", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("last_location", sa.JSON()),
    )


def downgrade():
    op.drop_table("ifood_driver_deliveries")
