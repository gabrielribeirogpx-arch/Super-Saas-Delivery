"""Save an address for verified email checkout accounts."""

from alembic import op
import sqlalchemy as sa

revision = "20261121_01_checkout_address"
down_revision = "20261120_01_customer_account"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("customer_email_accounts", sa.Column("checkout_address", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("customer_email_accounts", "checkout_address")
