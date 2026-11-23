"""Add tenant-scoped Wazza MCP credentials and privacy-safe audit."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261123_01_wazza_mcp_auth"
down_revision = "20261121_01_checkout_address"
branch_labels = None
depends_on = None


portable_json = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade():
    op.create_table(
        "wazza_mcp_credentials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key_id", sa.String(16), nullable=False, unique=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("scopes_json", portable_json, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("id", "tenant_id", name="uq_wazza_mcp_credential_id_tenant"),
        sa.CheckConstraint("length(key_id) = 16", name="ck_wazza_mcp_credential_key_id"),
        sa.CheckConstraint("length(token_hash) = 64", name="ck_wazza_mcp_credential_token_hash"),
    )
    op.create_index("ix_wazza_mcp_credentials_tenant_id", "wazza_mcp_credentials", ["tenant_id"])
    op.create_table(
        "wazza_mcp_audit_log",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("credential_id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.String(128), nullable=False),
        sa.Column("conversation_id", sa.String(128), nullable=True),
        sa.Column("tool_name", sa.String(100), nullable=False),
        sa.Column("risk", sa.String(20), nullable=False),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("error_code", sa.String(80), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("argument_keys_json", portable_json, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["credential_id", "tenant_id"],
            ["wazza_mcp_credentials.id", "wazza_mcp_credentials.tenant_id"],
            ondelete="RESTRICT",
            name="fk_wazza_mcp_audit_credential_tenant",
        ),
        sa.CheckConstraint("risk IN ('read','write','destructive')", name="ck_wazza_mcp_audit_risk"),
        sa.CheckConstraint("outcome IN ('success','denied','error')", name="ck_wazza_mcp_audit_outcome"),
        sa.CheckConstraint("duration_ms >= 0", name="ck_wazza_mcp_audit_duration"),
    )
    op.create_index("ix_wazza_mcp_audit_tenant_created", "wazza_mcp_audit_log", ["tenant_id", "created_at"])
    op.create_index("ix_wazza_mcp_audit_request", "wazza_mcp_audit_log", ["tenant_id", "request_id"])


def downgrade():
    op.drop_index("ix_wazza_mcp_audit_request", table_name="wazza_mcp_audit_log")
    op.drop_index("ix_wazza_mcp_audit_tenant_created", table_name="wazza_mcp_audit_log")
    op.drop_table("wazza_mcp_audit_log")
    op.drop_index("ix_wazza_mcp_credentials_tenant_id", table_name="wazza_mcp_credentials")
    op.drop_table("wazza_mcp_credentials")
