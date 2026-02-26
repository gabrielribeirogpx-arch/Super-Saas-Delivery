from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_tenant_banner_blur"
down_revision = "0005_tenant_public"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("tenants") as batch:
        batch.add_column(
            sa.Column(
                "banner_blur_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("tenants") as batch:
        batch.drop_column("banner_blur_enabled")
