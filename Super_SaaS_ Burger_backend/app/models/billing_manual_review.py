"""Trusted secondary evidence and durable human decision, never webhook payloads."""
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String
from app.core.database import Base


class BillingManualReview(Base):
    __tablename__ = "billing_manual_reviews"
    __table_args__ = (
        CheckConstraint("decision IS NULL OR decision IN ('approved','binding_approved','rejected')", name="ck_billing_review_decision"),
        CheckConstraint("decision IS NULL OR (decided_at IS NOT NULL AND decided_by IS NOT NULL)", name="ck_billing_review_actor"),
        CheckConstraint("(period_start IS NULL AND period_end IS NULL) OR (period_start IS NOT NULL AND period_end IS NOT NULL AND period_end > period_start)", name="ck_billing_review_period"),
    )
    billing_event_id = Column(Integer, ForeignKey("billing_events.id"), primary_key=True)
    # Only the official API/trusted source may write these evidence fields.
    sale_id = Column(String(255), nullable=True)
    product_id = Column(String(255), nullable=True)
    external_subscription_id = Column(String(255), nullable=True)
    external_offer_id = Column(String(255), nullable=True)
    sale_status = Column(String(30), nullable=True)
    sale_checked_at = Column(DateTime(timezone=True), nullable=True)
    period_start = Column(DateTime(timezone=True), nullable=True)
    period_end = Column(DateTime(timezone=True), nullable=True)
    period_source = Column(String(50), nullable=True)
    decision = Column(String(20), nullable=True)
    decided_by = Column(Integer, ForeignKey("admin_users.id"), nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(String(50), nullable=True)
