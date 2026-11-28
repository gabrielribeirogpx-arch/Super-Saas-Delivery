"""Store opt-in automatic acceptance of iFood orders."""

import sqlalchemy as sa
from alembic import op

revision = "20261128_05_ifood_auto_accept"
down_revision = "20261128_04_ifood_driver"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ifood_auto_accept",
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), primary_key=True),
        sa.Column("merchant_id", sa.String(36), primary_key=True),
        sa.Column("enabled_at", sa.DateTime(timezone=True)),
    )


def downgrade():
    op.drop_table("ifood_auto_accept")
