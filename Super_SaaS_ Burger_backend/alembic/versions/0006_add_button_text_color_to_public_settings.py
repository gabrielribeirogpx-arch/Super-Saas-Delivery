from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_button_text_color"
down_revision = "0005_tenant_public"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenant_public_settings",
        sa.Column("button_text_color", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenant_public_settings", "button_text_color")
