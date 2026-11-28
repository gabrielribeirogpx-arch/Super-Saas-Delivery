"""Persist outstanding iFood cancellation requests."""

import sqlalchemy as sa
from alembic import op

revision = "20261128_02_ifood_cancel"
down_revision = "20261128_01_ifood_connections"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("ifood_orders", sa.Column("cancellation_requested_at", sa.DateTime(timezone=True)))


def downgrade():
    op.drop_column("ifood_orders", "cancellation_requested_at")
