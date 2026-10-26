from sqlalchemy import Column, Integer, String, DateTime, Boolean, func

from app.core.database import Base


class CustomerStats(Base):
    __tablename__ = "customer_stats"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, index=True, nullable=False)
    phone = Column(String, index=True, nullable=False)
    total_orders = Column(Integer, default=0, nullable=False)
    total_spent = Column(Integer, default=0, nullable=False)
    last_order_at = Column(DateTime(timezone=True), nullable=True)
    opt_in = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
