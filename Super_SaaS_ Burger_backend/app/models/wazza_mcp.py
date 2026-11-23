"""Tenant-scoped credentials and privacy-safe audit for the Wazza MCP channel."""

from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


PortableJSON = sa.JSON().with_variant(JSONB(), "postgresql")


class WazzaMcpCredential(Base):
    __tablename__ = "wazza_mcp_credentials"
    __table_args__ = (
        sa.UniqueConstraint("id", "tenant_id", name="uq_wazza_mcp_credential_id_tenant"),
        sa.CheckConstraint("length(key_id) = 16", name="ck_wazza_mcp_credential_key_id"),
        sa.CheckConstraint("length(token_hash) = 64", name="ck_wazza_mcp_credential_token_hash"),
    )

    id = sa.Column(sa.Integer, primary_key=True)
    tenant_id = sa.Column(sa.Integer, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    key_id = sa.Column(sa.String(16), nullable=False, unique=True)
    token_hash = sa.Column(sa.String(64), nullable=False, unique=True)
    name = sa.Column(sa.String(120), nullable=False)
    scopes_json = sa.Column(PortableJSON, nullable=False)
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False, default=utc_now)
    expires_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    last_used_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    revoked_at = sa.Column(sa.DateTime(timezone=True), nullable=True)


class WazzaMcpAuditLog(Base):
    __tablename__ = "wazza_mcp_audit_log"
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["credential_id", "tenant_id"],
            ["wazza_mcp_credentials.id", "wazza_mcp_credentials.tenant_id"],
            ondelete="RESTRICT",
            name="fk_wazza_mcp_audit_credential_tenant",
        ),
        sa.CheckConstraint("risk IN ('read','write','destructive')", name="ck_wazza_mcp_audit_risk"),
        sa.CheckConstraint("outcome IN ('success','denied','error')", name="ck_wazza_mcp_audit_outcome"),
        sa.CheckConstraint("duration_ms >= 0", name="ck_wazza_mcp_audit_duration"),
        sa.Index("ix_wazza_mcp_audit_tenant_created", "tenant_id", "created_at"),
        sa.Index("ix_wazza_mcp_audit_request", "tenant_id", "request_id"),
    )

    id = sa.Column(sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True)
    tenant_id = sa.Column(sa.Integer, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    credential_id = sa.Column(sa.Integer, nullable=False)
    request_id = sa.Column(sa.String(128), nullable=False)
    conversation_id = sa.Column(sa.String(128), nullable=True)
    tool_name = sa.Column(sa.String(100), nullable=False)
    risk = sa.Column(sa.String(20), nullable=False)
    outcome = sa.Column(sa.String(20), nullable=False)
    error_code = sa.Column(sa.String(80), nullable=True)
    duration_ms = sa.Column(sa.Integer, nullable=False, default=0)
    argument_keys_json = sa.Column(PortableJSON, nullable=False, default=list)
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False, default=utc_now)


class WazzaOrderDraft(Base):
    """Isolated cart state; a draft is never an operational order."""

    __tablename__ = "wazza_order_drafts"
    __table_args__ = (
        sa.UniqueConstraint("public_id", name="uq_wazza_order_draft_public_id"),
        sa.CheckConstraint("status IN ('active','expired','confirmed')", name="ck_wazza_order_draft_status"),
        sa.CheckConstraint("version >= 1", name="ck_wazza_order_draft_version"),
        sa.Index("ix_wazza_order_draft_owner", "tenant_id", "owner_hash", "status"),
        sa.Index("ix_wazza_order_draft_expires", "expires_at"),
        sa.ForeignKeyConstraint(
            ["confirmed_order_id", "tenant_id"], ["orders.id", "orders.tenant_id"],
            name="fk_wazza_draft_confirmed_order_tenant",
        ),
        sa.UniqueConstraint("tenant_id", "confirmation_key_hash", name="uq_wazza_draft_confirmation_key"),
        sa.UniqueConstraint("confirmed_order_id", name="uq_wazza_draft_confirmed_order"),
        sa.CheckConstraint(
            "(status = 'confirmed' AND confirmed_order_id IS NOT NULL AND confirmed_at IS NOT NULL "
            "AND confirmation_key_hash IS NOT NULL AND confirmation_request_hash IS NOT NULL) OR "
            "(status <> 'confirmed' AND confirmed_order_id IS NULL AND confirmed_at IS NULL "
            "AND confirmation_key_hash IS NULL AND confirmation_request_hash IS NULL)",
            name="ck_wazza_draft_confirmation",
        ),
    )

    id = sa.Column(sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True)
    public_id = sa.Column(sa.String(32), nullable=False)
    tenant_id = sa.Column(sa.Integer, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    owner_hash = sa.Column(sa.String(64), nullable=False)
    conversation_hash = sa.Column(sa.String(64), nullable=True)
    status = sa.Column(sa.String(20), nullable=False, default="active")
    items_json = sa.Column(PortableJSON, nullable=False, default=list)
    fulfillment_json = sa.Column(PortableJSON, nullable=True)
    payment_json = sa.Column(PortableJSON, nullable=True)
    mutation_keys_json = sa.Column(PortableJSON, nullable=False, default=dict)
    version = sa.Column(sa.Integer, nullable=False, default=1)
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = sa.Column(sa.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)
    expires_at = sa.Column(sa.DateTime(timezone=True), nullable=False)
    confirmed_order_id = sa.Column(sa.Integer, nullable=True)
    confirmed_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    confirmation_key_hash = sa.Column(sa.String(64), nullable=True)
    confirmation_request_hash = sa.Column(sa.String(64), nullable=True)
