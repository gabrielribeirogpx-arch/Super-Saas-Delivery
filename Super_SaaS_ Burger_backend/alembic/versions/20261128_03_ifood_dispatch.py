"""Persist requested dispatches for iFood orders."""

import sqlalchemy as sa
from alembic import op

revision = "20261128_03_ifood_dispatch"
down_revision = "20261128_02_ifood_cancel"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("ifood_orders", sa.Column("dispatch_requested_at", sa.DateTime(timezone=True)))


def downgrade():
    op.drop_column("ifood_orders", "dispatch_requested_at")
