"""Store a revocable fiscal delegation per store."""

import sqlalchemy as sa
from alembic import op

revision = "20261127_04_fiscal_access"
down_revision = "20261127_03_focus_company"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("fiscal_profiles") as batch:
        batch.add_column(sa.Column("delegate_digest", sa.String(64), nullable=True))
        batch.add_column(sa.Column("delegate_expires_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_index("ix_fiscal_profiles_delegate_digest", ["delegate_digest"], unique=True)


def downgrade():
    with op.batch_alter_table("fiscal_profiles") as batch:
        batch.drop_index("ix_fiscal_profiles_delegate_digest")
        batch.drop_column("delegate_expires_at")
        batch.drop_column("delegate_digest")
