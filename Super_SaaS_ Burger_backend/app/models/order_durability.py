"""Transactional checkout receipts and restart-safe operational effects."""
from datetime import datetime, timezone
from sqlalchemy import (BigInteger, CheckConstraint, Column, DateTime, ForeignKey,
                        ForeignKeyConstraint, Integer, JSON, String, UniqueConstraint, Index)
from sqlalchemy.dialects.postgresql import JSONB
from app.core.database import Base


def now_utc():
    return datetime.now(timezone.utc)


class OrderSubmission(Base):
    __tablename__ = "order_submissions"
    __table_args__ = (
        ForeignKeyConstraint(["order_id", "tenant_id"], ["orders.id", "orders.tenant_id"], ondelete="CASCADE"),
        CheckConstraint("length(key_hash) = 64 AND length(request_hash) = 64", name="ck_order_submission_hashes"),
        CheckConstraint("(order_id IS NULL AND response_json IS NULL) OR (order_id IS NOT NULL AND response_json IS NOT NULL)", name="ck_order_submission_result"),
        Index("ix_order_submissions_expiry", "expires_at"),
    )
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    key_hash = Column(String(64), primary_key=True)
    request_hash = Column(String(64), nullable=False)
    order_id = Column(Integer, nullable=True)
    response_json = Column(JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_utc)
    expires_at = Column(DateTime(timezone=True), nullable=False)


class OrderOutbox(Base):
    __tablename__ = "order_outbox"
    __table_args__ = (
        ForeignKeyConstraint(["order_id", "tenant_id"], ["orders.id", "orders.tenant_id"], ondelete="CASCADE"),
        UniqueConstraint("event_key", "effect", name="uq_order_outbox_event_effect"),
        CheckConstraint("status IN ('pending','processing','done','review')", name="ck_order_outbox_status"),
        CheckConstraint("attempts >= 0", name="ck_order_outbox_attempts"),
        Index("ix_order_outbox_due", "status", "next_attempt_at", "id"),
        Index("ix_order_outbox_stream", "tenant_id", "order_id", "stream", "id"),
        Index("ix_order_outbox_completed", "status", "completed_at"),
    )
    id = Column(BigInteger().with_variant(Integer(), "sqlite"), primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    order_id = Column(Integer, nullable=False)
    event_key = Column(String(32), nullable=False)
    effect = Column(String(40), nullable=False)
    stream = Column(String(20), nullable=False)
    payload = Column(JSON().with_variant(JSONB(), "postgresql"), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    attempts = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(DateTime(timezone=True), nullable=False, default=now_utc)
    lease_token = Column(String(32), nullable=True)
    lease_until = Column(DateTime(timezone=True), nullable=True)
    error_code = Column(String(80), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=now_utc)
    completed_at = Column(DateTime(timezone=True), nullable=True)


class OrderEffectReceipt(Base):
    __tablename__ = "order_effect_receipts"
    __table_args__ = (
        ForeignKeyConstraint(["order_id", "tenant_id"], ["orders.id", "orders.tenant_id"], ondelete="CASCADE"),
    )
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    order_id = Column(Integer, primary_key=True)
    effect_key = Column(String(80), primary_key=True)
    completed_at = Column(DateTime(timezone=True), nullable=False, default=now_utc)
