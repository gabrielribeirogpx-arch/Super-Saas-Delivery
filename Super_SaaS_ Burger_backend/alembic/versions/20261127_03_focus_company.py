"""Bind a fiscal profile to a Focus company."""

import sqlalchemy as sa
from alembic import op

revision = "20261127_03_focus_company"
down_revision = "20261127_02_fiscal_profiles"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("fiscal_profiles") as batch:
        batch.add_column(sa.Column("focus_company_id", sa.Integer(), nullable=True))
        batch.create_unique_constraint("uq_fiscal_profiles_focus_company", ["focus_company_id"])


def downgrade():
    with op.batch_alter_table("fiscal_profiles") as batch:
        batch.drop_constraint("uq_fiscal_profiles_focus_company", type_="unique")
        batch.drop_column("focus_company_id")
