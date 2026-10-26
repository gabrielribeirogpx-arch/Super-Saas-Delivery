from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func, true

from app.core.database import Base


class BillingOfferMapping(Base):
    __tablename__ = "billing_offer_mappings"
    __table_args__ = (
        UniqueConstraint("provider", "environment", "provider_account_id", "external_product_id", "external_offer_id", name="uq_billing_offer_external"),
        CheckConstraint("environment IN ('sandbox', 'production')", name="ck_billing_offer_environment"),
        CheckConstraint("length(provider) > 0 AND length(provider_account_id) > 0 AND length(external_product_id) > 0 AND length(external_offer_id) > 0", name="ck_billing_offer_identity"),
    )

    id = Column(Integer, primary_key=True)
    provider = Column(String(50), nullable=False)
    environment = Column(String(20), nullable=False)
    provider_account_id = Column(String(255), nullable=False)
    external_product_id = Column(String(255), nullable=False)
    external_offer_id = Column(String(255), nullable=False)
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=False)
    active = Column(Boolean, nullable=False, default=True, server_default=true())
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
