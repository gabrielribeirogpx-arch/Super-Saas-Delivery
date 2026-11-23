"""Add isolated Wazza order drafts."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261123_02_wazza_order_drafts"
down_revision = "20261123_01_wazza_mcp_auth"
branch_labels = None
depends_on = None

portable_json = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade():
    op.create_table(
        "wazza_order_drafts",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True),
        sa.Column("public_id", sa.String(32), nullable=False),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_hash", sa.String(64), nullable=False),
        sa.Column("conversation_hash", sa.String(64), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("items_json", portable_json, nullable=False),
        sa.Column("fulfillment_json", portable_json, nullable=True),
        sa.Column("payment_json", portable_json, nullable=True),
        sa.Column("mutation_keys_json", portable_json, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("public_id", name="uq_wazza_order_draft_public_id"),
        sa.CheckConstraint("status IN ('active','expired','confirmed')", name="ck_wazza_order_draft_status"),
        sa.CheckConstraint("version >= 1", name="ck_wazza_order_draft_version"),
    )
    op.create_index("ix_wazza_order_draft_owner", "wazza_order_drafts", ["tenant_id", "owner_hash", "status"])
    op.create_index("ix_wazza_order_draft_expires", "wazza_order_drafts", ["expires_at"])


def downgrade():
    op.drop_index("ix_wazza_order_draft_expires", table_name="wazza_order_drafts")
    op.drop_index("ix_wazza_order_draft_owner", table_name="wazza_order_drafts")
    op.drop_table("wazza_order_drafts")
