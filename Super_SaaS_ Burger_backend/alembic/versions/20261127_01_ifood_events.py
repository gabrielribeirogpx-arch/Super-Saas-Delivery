"""Store the iFood pilot event inbox."""

import sqlalchemy as sa
from alembic import op

revision = "20261127_01_ifood_events"
down_revision = "20261126_01_ticket_paper_width"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ifood_events",
        sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("merchant_id", sa.String(36), nullable=False),
        sa.Column("order_id", sa.String(36)),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ifood_events_tenant_order", "ifood_events", ["tenant_id", "order_id"])


def downgrade():
    op.drop_index("ix_ifood_events_tenant_order", table_name="ifood_events")
    op.drop_table("ifood_events")
