from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_manual_open_status"
down_revision = "0005_tenant_public"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("manual_open_status", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.alter_column("tenants", "manual_open_status", server_default=None)


def downgrade() -> None:
    op.drop_column("tenants", "manual_open_status")
