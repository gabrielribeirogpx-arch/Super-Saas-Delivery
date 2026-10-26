from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text

from app.core.database import Base


class ModifierGroup(Base):
    __tablename__ = "modifier_groups"
    __table_args__ = (Index("ix_modifier_groups_tenant", "tenant_id"),)

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, index=True, nullable=False)
    product_id = Column(Integer, ForeignKey("menu_items.id"), nullable=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    required = Column(Boolean, default=False, nullable=False)
    min_selection = Column(Integer, default=0, nullable=False)
    max_selection = Column(Integer, default=1, nullable=False)
    order_index = Column(Integer, default=0, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
