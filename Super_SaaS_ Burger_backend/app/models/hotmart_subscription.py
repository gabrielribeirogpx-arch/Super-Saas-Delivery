"""Scoped provider bindings and durable cancellation requests, never buyer PII."""
from sqlalchemy import Column, DateTime, ForeignKey, ForeignKeyConstraint, Integer, String, UniqueConstraint, CheckConstraint, func
from app.core.database import Base

class HotmartSubscription(Base):
    __tablename__ = "hotmart_subscriptions"
    __table_args__ = (
        UniqueConstraint("account_id", "environment", "subscriber_code", name="uq_hotmart_subscriber_scope"),
        UniqueConstraint("tenant_id", name="uq_hotmart_tenant"),
        ForeignKeyConstraint(["subscription_id", "tenant_id"], ["subscriptions.id", "subscriptions.tenant_id"], name="fk_hotmart_subscription_tenant"),
        CheckConstraint("environment IN ('sandbox','production')", name="ck_hotmart_environment"),
        CheckConstraint("cancel_status IN ('none','pending','confirmed')", name="ck_hotmart_cancel_status"),
    )
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    subscription_id = Column(Integer, nullable=False)
    account_id = Column(String(255), nullable=False)
    environment = Column(String(20), nullable=False)
    subscriber_code = Column(String(255), nullable=False)
    product_id = Column(String(255), nullable=False)
    external_plan_id = Column(String(255), nullable=False)
    last_transaction = Column(String(255), nullable=True)
    reconcile_at = Column(DateTime(timezone=True), nullable=True)
    last_event_at = Column(DateTime(timezone=True), nullable=True)
    cancel_status = Column(String(20), nullable=False, default="none", server_default="none")
    cancel_requested_by = Column(Integer, ForeignKey("admin_users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
