"""Store a fiscal onboarding profile per tenant."""

import sqlalchemy as sa
from alembic import op

revision = "20261127_02_fiscal_profiles"
down_revision = "20261127_01_ifood_events"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "fiscal_profiles",
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("cnpj", sa.String(14), nullable=False),
        sa.Column("legal_name", sa.String(120), nullable=False),
        sa.Column("state_registration", sa.String(14), nullable=False),
        sa.Column("state_code", sa.String(2), nullable=False),
        sa.Column("tax_regime", sa.Integer(), nullable=False),
    )


def downgrade():
    op.drop_table("fiscal_profiles")
