from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text, func

from app.core.database import Base


class CustomerBenefit(Base):
    __tablename__ = "customer_benefits"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    benefit_type = Column(String(40), nullable=False, index=True)
    title = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    benefit_value = Column(Numeric(10, 2), nullable=True)
    coupon_code = Column(String(80), nullable=True)
    active = Column(Boolean, nullable=False, default=True, server_default="1")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
