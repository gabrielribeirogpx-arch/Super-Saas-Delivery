"""Timestamp imported iFood orders for the automatic acceptance delay."""

import sqlalchemy as sa
from alembic import op

revision = "20261128_06_ifood_imported_at"
down_revision = "20261128_05_ifood_auto_accept"
branch_labels = None
depends_on = None


def upgrade():
    # Keep existing imports eligible on their original schedule.
    op.add_column("ifood_orders", sa.Column("imported_at", sa.DateTime(timezone=True)))


def downgrade():
    op.drop_column("ifood_orders", "imported_at")
