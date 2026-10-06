from enum import Enum

from sqlalchemy import Boolean, Column, DateTime, Enum as SAEnum, ForeignKey, Integer, String, UniqueConstraint, func

from app.core.database import Base


class SubscriptionStatus(str, Enum):
    INACTIVE = "inactive"
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    EXPIRED = "expired"


class Subscription(Base):
    __tablename__ = "subscriptions"
    # One current internal subscription per tenant; provider event history is future work.
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_subscriptions_tenant"),)

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=False)
    provider = Column(String(50), nullable=True)
    provider_subscription_id = Column(String(255), nullable=True)
    provider_customer_id = Column(String(255), nullable=True)
    status = Column(SAEnum(SubscriptionStatus, values_callable=lambda enum: [item.value for item in enum],
                           name="subscription_status", native_enum=False, create_constraint=True,
                           validate_strings=True), nullable=False, default=SubscriptionStatus.INACTIVE,
                    server_default="inactive")
    current_period_start = Column(DateTime(timezone=True), nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    trial_end = Column(DateTime(timezone=True), nullable=True)
    canceled_at = Column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end = Column(Boolean, nullable=False, default=False, server_default="0")
    past_due_since = Column(DateTime(timezone=True), nullable=True)
    grace_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
