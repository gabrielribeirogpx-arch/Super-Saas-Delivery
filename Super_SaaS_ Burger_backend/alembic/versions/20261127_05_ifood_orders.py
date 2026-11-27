"""Store imported iFood pilot orders."""

import sqlalchemy as sa
from alembic import op

revision = "20261127_05_ifood_orders"
down_revision = "20261127_04_fiscal_access"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ifood_orders",
        sa.Column("order_id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("merchant_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("confirmation_requested_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_ifood_orders_tenant_id", "ifood_orders", ["tenant_id"])


def downgrade():
    op.drop_index("ix_ifood_orders_tenant_id", table_name="ifood_orders")
    op.drop_table("ifood_orders")
