from sqlalchemy import Boolean, Column, ForeignKey, Integer, Numeric, String, Text

from app.core.database import Base


class ModifierOption(Base):
    __tablename__ = "modifier_options"

    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("modifier_groups.id"), index=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    price_delta = Column(Numeric(10, 2), default=0, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    order_index = Column(Integer, default=0, nullable=False)
