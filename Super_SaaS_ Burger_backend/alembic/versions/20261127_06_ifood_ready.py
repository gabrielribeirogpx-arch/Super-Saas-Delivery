"""Record iFood ready-for-pickup requests."""

import sqlalchemy as sa
from alembic import op

revision = "20261127_06_ifood_ready"
down_revision = "20261127_05_ifood_orders"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("ifood_orders", sa.Column("ready_requested_at", sa.DateTime(timezone=True)))


def downgrade():
    op.drop_column("ifood_orders", "ready_requested_at")
