from enum import Enum

from sqlalchemy import CheckConstraint, Column, DateTime, Enum as SAEnum, ForeignKey, ForeignKeyConstraint, Integer, String, Text, UniqueConstraint, func

from app.core.database import Base


class BillingEventStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


class BillingEvent(Base):
    __tablename__ = "billing_events"
    __table_args__ = (
        UniqueConstraint("provider", "provider_account_id", "environment", "provider_event_id", name="uq_billing_event_identity"),
        ForeignKeyConstraint(["subscription_id", "tenant_id"], ["subscriptions.id", "subscriptions.tenant_id"], name="fk_billing_event_subscription_tenant"),
        ForeignKeyConstraint(["checkout_intent_id", "tenant_id"], ["billing_checkout_intents.id", "billing_checkout_intents.tenant_id"], name="fk_billing_event_intent_tenant"),
        CheckConstraint("environment IN ('sandbox', 'production')", name="ck_billing_event_environment"),
        CheckConstraint("length(provider) > 0 AND length(provider_account_id) > 0 AND length(provider_event_id) > 0", name="ck_billing_event_identity"),
        CheckConstraint("length(payload_hash) = 64", name="ck_billing_event_hash"),
        CheckConstraint("attempt_count >= 0 AND schema_version >= 1", name="ck_billing_event_attempts_schema"),
        CheckConstraint("(subscription_id IS NULL AND checkout_intent_id IS NULL) OR tenant_id IS NOT NULL", name="ck_billing_event_links_tenant"),
        CheckConstraint("processing_status != 'processed' OR processed_at IS NOT NULL", name="ck_billing_event_processed"),
    )

    id = Column(Integer, primary_key=True)
    provider = Column(String(50), nullable=False)
    environment = Column(String(20), nullable=False)
    provider_account_id = Column(String(255), nullable=False)
    provider_event_id = Column(String(255), nullable=False)
    event_type = Column(String(100), nullable=False)
    schema_version = Column(Integer, nullable=False, default=1, server_default="1")
    payload_hash = Column(String(64), nullable=False)
    # Only a redacted receipt is stored by the service, never the original payload.
    raw_payload = Column(Text, nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=True)
    received_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)
    processing_status = Column(SAEnum(BillingEventStatus, values_callable=lambda enum: [s.value for s in enum], native_enum=False,
                                    create_constraint=True, validate_strings=True, name="billing_event_status"),
                               nullable=False, default=BillingEventStatus.PENDING, server_default="pending", index=True)
    attempt_count = Column(Integer, nullable=False, default=0, server_default="0")
    next_attempt_at = Column(DateTime(timezone=True), nullable=True)
    error_code = Column(String(100), nullable=True)
    error_message = Column(String(255), nullable=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", name="fk_billing_event_tenant"), nullable=True, index=True)
    subscription_id = Column(Integer, nullable=True)
    checkout_intent_id = Column(Integer, nullable=True)
