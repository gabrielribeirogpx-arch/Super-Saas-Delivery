from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, func

from app.core.database import Base


class MenuItem(Base):
    __tablename__ = "menu_items"
    __table_args__ = (Index("ix_menu_items_tenant_category", "tenant_id", "category_id"),)

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, index=True, nullable=False)
    category_id = Column(Integer, ForeignKey("menu_categories.id"), nullable=True)
    name = Column(String, nullable=False)
    price_cents = Column(Integer, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
