"""Persistent native-payment foundation; current writer is sandbox simulation only."""
from sqlalchemy import (
    BigInteger, CheckConstraint, Column, DateTime, ForeignKey,
    ForeignKeyConstraint, Integer, JSON, String, UniqueConstraint, func,
)

from app.core.database import Base


class NativePaymentIntent(Base):
    __tablename__ = "native_payment_intents"
    __table_args__ = (
        ForeignKeyConstraint(["order_id", "tenant_id"], ["orders.id", "orders.tenant_id"], name="fk_native_intent_order_tenant"),
        UniqueConstraint("tenant_id", "order_id", name="uq_native_intent_tenant_order"),
        UniqueConstraint("id", "tenant_id", name="uq_native_intent_id_tenant"),
        UniqueConstraint("public_id", name="uq_native_intent_public"),
        CheckConstraint("environment = 'sandbox' AND provider = 'internal_simulation'", name="ck_native_intent_simulation"),
        CheckConstraint("status IN ('pending','paid','failed','canceled','refunded')", name="ck_native_intent_status"),
        CheckConstraint("settlement_status = 'not_settled'", name="ck_native_intent_not_settled"),
        CheckConstraint("currency = 'BRL' AND total_cents > 0 AND platform_fee_cents >= 0 AND merchant_before_psp_cents >= 0 AND total_cents = platform_fee_cents + merchant_before_psp_cents", name="ck_native_intent_amounts"),
        CheckConstraint("length(snapshot_hash) = 64", name="ck_native_intent_hash"),
        CheckConstraint("status NOT IN ('paid','refunded') OR paid_at IS NOT NULL", name="ck_native_intent_paid_at"),
        CheckConstraint("status != 'refunded' OR refunded_at IS NOT NULL", name="ck_native_intent_refunded_at"),
    )
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    order_id = Column(Integer, nullable=False)
    public_id = Column(String(64), nullable=False)
    provider = Column(String(40), nullable=False, default="internal_simulation", server_default="internal_simulation")
    environment = Column(String(20), nullable=False, default="sandbox", server_default="sandbox")
    status = Column(String(20), nullable=False, default="pending", server_default="pending")
    settlement_status = Column(String(20), nullable=False, default="not_settled", server_default="not_settled")
    currency = Column(String(3), nullable=False, default="BRL", server_default="BRL")
    total_cents = Column(BigInteger, nullable=False)
    platform_fee_cents = Column(BigInteger, nullable=False)
    merchant_before_psp_cents = Column(BigInteger, nullable=False)
    snapshot = Column(JSON, nullable=False)
    snapshot_hash = Column(String(64), nullable=False)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    refunded_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class NativePaymentAttempt(Base):
    __tablename__ = "native_payment_attempts"
    __table_args__ = (
        ForeignKeyConstraint(["intent_id", "tenant_id"], ["native_payment_intents.id", "native_payment_intents.tenant_id"], name="fk_native_attempt_intent_tenant"),
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_native_attempt_idempotency"),
        UniqueConstraint("intent_id", "attempt_number", name="uq_native_attempt_number"),
        CheckConstraint("attempt_number > 0 AND length(idempotency_key) > 0", name="ck_native_attempt_identity"),
        CheckConstraint("status IN ('pending','paid','failed','canceled','refunded')", name="ck_native_attempt_status"),
    )
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    intent_id = Column(Integer, nullable=False)
    attempt_number = Column(Integer, nullable=False)
    idempotency_key = Column(String(120), nullable=False)
    status = Column(String(20), nullable=False, default="pending", server_default="pending")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class NativePaymentEvent(Base):
    __tablename__ = "native_payment_events"
    __table_args__ = (
        ForeignKeyConstraint(["intent_id", "tenant_id"], ["native_payment_intents.id", "native_payment_intents.tenant_id"], name="fk_native_event_intent_tenant"),
        UniqueConstraint("tenant_id", "external_event_id", name="uq_native_event_identity"),
        UniqueConstraint("id", "tenant_id", "intent_id", name="uq_native_event_owner"),
        CheckConstraint("length(payload_hash) = 64 AND length(external_event_id) > 0", name="ck_native_event_identity"),
        CheckConstraint("target_status IN ('paid','failed','canceled','refunded')", name="ck_native_event_status"),
        CheckConstraint("currency = 'BRL' AND amount_cents > 0", name="ck_native_event_amount"),
    )
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    intent_id = Column(Integer, nullable=False)
    external_event_id = Column(String(120), nullable=False)
    payload_hash = Column(String(64), nullable=False)
    target_status = Column(String(20), nullable=False)
    amount_cents = Column(BigInteger, nullable=False)
    currency = Column(String(3), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class NativePaymentLedger(Base):
    __tablename__ = "native_payment_ledger"
    __table_args__ = (
        ForeignKeyConstraint(["intent_id", "tenant_id"], ["native_payment_intents.id", "native_payment_intents.tenant_id"], name="fk_native_ledger_intent_tenant"),
        ForeignKeyConstraint(["event_id", "tenant_id", "intent_id"], ["native_payment_events.id", "native_payment_events.tenant_id", "native_payment_events.intent_id"], name="fk_native_ledger_event_owner"),
        UniqueConstraint("intent_id", "kind", name="uq_native_ledger_kind"),
        CheckConstraint("kind IN ('payment','refund')", name="ck_native_ledger_kind"),
        CheckConstraint("gross_delta_cents = platform_fee_delta_cents + merchant_delta_cents", name="ck_native_ledger_balanced"),
        CheckConstraint("(kind = 'payment' AND gross_delta_cents > 0 AND platform_fee_delta_cents >= 0 AND merchant_delta_cents >= 0) OR (kind = 'refund' AND gross_delta_cents < 0 AND platform_fee_delta_cents <= 0 AND merchant_delta_cents <= 0)", name="ck_native_ledger_sign"),
    )
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    intent_id = Column(Integer, nullable=False)
    event_id = Column(Integer, nullable=False)
    kind = Column(String(20), nullable=False)
    gross_delta_cents = Column(BigInteger, nullable=False)
    platform_fee_delta_cents = Column(BigInteger, nullable=False)
    merchant_delta_cents = Column(BigInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
