from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, index=True, nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"), index=True, nullable=False)
    menu_item_id = Column(Integer, nullable=True)

    name = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price_cents = Column(Integer, nullable=False, default=0)
    subtotal_cents = Column(Integer, nullable=False, default=0)
    modifiers_json = Column(Text, nullable=True)
    production_area = Column(String, nullable=False, default="COZINHA")

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    order = relationship("Order", back_populates="order_items")
