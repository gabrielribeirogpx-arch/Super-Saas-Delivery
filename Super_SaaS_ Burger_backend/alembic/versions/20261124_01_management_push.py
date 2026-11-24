"""Persist Android management push subscriptions."""
import sqlalchemy as sa
from alembic import op

revision = "20261124_01_management_push"
down_revision = "20261123_04_wazza_mutations"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "management_push_devices",
        sa.Column("token", sa.String(512), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("admin_user_id", sa.Integer(), sa.ForeignKey("admin_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("credential_version", sa.Integer(), nullable=False),
        sa.Column("binding", sa.String(36), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_management_push_devices_tenant_id", "management_push_devices", ["tenant_id"])


def downgrade():
    op.drop_table("management_push_devices")
