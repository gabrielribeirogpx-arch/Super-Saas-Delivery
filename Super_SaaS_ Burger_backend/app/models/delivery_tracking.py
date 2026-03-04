from sqlalchemy import Column, DateTime, ForeignKey, Integer, func

from app.core.database import Base


class DeliveryTracking(Base):
    __tablename__ = "delivery_tracking"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), index=True, nullable=False)
    delivery_user_id = Column(Integer, ForeignKey("admin_users.id", ondelete="SET NULL"), index=True, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    estimated_duration_seconds = Column(Integer, nullable=False)
    expected_delivery_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
