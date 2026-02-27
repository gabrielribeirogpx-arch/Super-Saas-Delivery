from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_estimated_prep_time"
down_revision = "0006_manual_open_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("estimated_prep_time", sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "estimated_prep_time")
