"""Store OAuth connections for authorized iFood merchants."""

import sqlalchemy as sa
from alembic import op

revision = "20261128_01_ifood_connections"
down_revision = "20261127_06_ifood_ready"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ifood_connections",
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), primary_key=True),
        sa.Column("merchant_id", sa.String(36), nullable=False, unique=True),
        sa.Column("merchant_name", sa.String(255), nullable=False),
        sa.Column("encrypted_tokens", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("ifood_connections")
