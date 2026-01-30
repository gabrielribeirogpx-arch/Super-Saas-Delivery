from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class OrderPayment(Base):
    __tablename__ = "order_payments"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, index=True, nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"), index=True, nullable=False)

    method = Column(String, nullable=False)
    amount_cents = Column(Integer, nullable=False)
    fee_cents = Column(Integer, nullable=False, default=0)
    status = Column(String, nullable=False, default="paid")
    paid_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    order = relationship("Order", back_populates="payments")


class CashMovement(Base):
    __tablename__ = "cash_movements"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, index=True, nullable=False)

    type = Column(String, nullable=False)
    category = Column(String, nullable=False)
    description = Column(String, nullable=True)
    amount_cents = Column(Integer, nullable=False)
    reference_type = Column(String, nullable=True)
    reference_id = Column(Integer, nullable=True)
    occurred_at = Column(DateTime(timezone=True), index=True, server_default=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
