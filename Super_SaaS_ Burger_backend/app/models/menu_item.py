from sqlalchemy import Boolean, Column, DateTime, Integer, String, func

from app.core.database import Base


class MenuItem(Base):
    __tablename__ = "menu_items"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, index=True, nullable=False)
    name = Column(String, nullable=False)
    price_cents = Column(Integer, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
