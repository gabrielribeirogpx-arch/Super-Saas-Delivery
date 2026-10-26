from sqlalchemy import Boolean, CheckConstraint, Column, Integer, ForeignKey, String, UniqueConstraint

from app.core.database import Base


class PlanEntitlement(Base):
    __tablename__ = "plan_entitlements"
    __table_args__ = (
        UniqueConstraint("plan_id", "feature_code", name="uq_plan_entitlements_plan_feature"),
        CheckConstraint("limit_value IS NULL OR limit_value >= 0", name="ck_plan_entitlements_limit"),
        CheckConstraint("reset_period IS NULL OR reset_period = 'monthly'", name="ck_plan_entitlements_reset"),
    )

    id = Column(Integer, primary_key=True)
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=False)
    feature_code = Column(String(50), nullable=False)
    enabled = Column(Boolean, nullable=False, default=False, server_default="0")
    # NULL = unlimited; 0 = no capacity; enabled=False = disabled feature.
    limit_value = Column(Integer, nullable=True)
    reset_period = Column(String(20), nullable=True)
