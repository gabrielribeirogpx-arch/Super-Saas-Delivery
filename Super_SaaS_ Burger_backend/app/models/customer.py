from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("tenant_id", "phone_normalized", name="ux_customers_tenant_phone_normalized"),)

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String(120), nullable=True)
    phone = Column(String(30), nullable=False, index=True)
    phone_normalized = Column(String(32), nullable=True, index=True)
    email = Column(String(150), nullable=True)
    phone_verified_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    addresses = relationship("CustomerAddress", back_populates="customer", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="customer")
    points = relationship("CustomerPoints", back_populates="customer", uselist=False)
    benefits = relationship("CustomerBenefit", back_populates="customer")
    tags = relationship("CustomerTag", back_populates="customer")
