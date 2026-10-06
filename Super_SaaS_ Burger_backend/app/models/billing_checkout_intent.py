import secrets
from enum import Enum

from sqlalchemy import CheckConstraint, Column, DateTime, Enum as SAEnum, ForeignKey, Integer, String, UniqueConstraint, func

from app.core.database import Base


def generate_checkout_token() -> str:
    return secrets.token_urlsafe(32)


class BillingIntentStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    EXPIRED = "expired"
    CANCELED = "canceled"


class BillingCheckoutIntent(Base):
    __tablename__ = "billing_checkout_intents"
    __table_args__ = (
        UniqueConstraint("public_token", name="uq_billing_intent_token"),
        UniqueConstraint("provider", "provider_account_id", "environment", "external_checkout_id", name="uq_billing_intent_external_checkout"),
        UniqueConstraint("id", "tenant_id", name="uq_billing_intent_id_tenant"),
        CheckConstraint("environment IN ('sandbox', 'production')", name="ck_billing_intent_environment"),
        CheckConstraint("length(public_token) >= 43 AND length(provider) > 0 AND length(provider_account_id) > 0", name="ck_billing_intent_identity"),
        CheckConstraint("status != 'completed' OR completed_at IS NOT NULL", name="ck_billing_intent_completed"),
    )

    id = Column(Integer, primary_key=True)
    public_token = Column(String(64), nullable=False, default=generate_checkout_token)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=False)
    provider = Column(String(50), nullable=False)
    provider_account_id = Column(String(255), nullable=False)
    environment = Column(String(20), nullable=False)
    status = Column(SAEnum(BillingIntentStatus, values_callable=lambda enum: [s.value for s in enum], native_enum=False,
                         create_constraint=True, validate_strings=True, name="billing_intent_status"),
                    nullable=False, default=BillingIntentStatus.PENDING, server_default="pending")
    external_checkout_id = Column(String(255), nullable=True)
    external_customer_id = Column(String(255), nullable=True)
    external_subscription_id = Column(String(255), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
