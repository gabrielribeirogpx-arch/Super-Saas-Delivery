"""Track public owner email verification without changing existing accounts."""
from alembic import op
import sqlalchemy as sa

revision = "20261119_01_owner_email"
down_revision = "20261023_02_order_durability"
branch_labels = None
depends_on = None


def upgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("admin_users")}
    if "email_verification_required" not in columns:
        op.add_column("admin_users", sa.Column("email_verification_required", sa.Boolean(), nullable=False, server_default="0"))
    if "email_verified_at" not in columns:
        op.add_column("admin_users", sa.Column("email_verified_at", sa.DateTime(timezone=True)))
    if "email_verification_sent_at" not in columns:
        op.add_column("admin_users", sa.Column("email_verification_sent_at", sa.DateTime(timezone=True)))


def downgrade():
    op.drop_column("admin_users", "email_verification_sent_at")
    op.drop_column("admin_users", "email_verified_at")
    op.drop_column("admin_users", "email_verification_required")
