from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func

from app.core.database import Base


class Modifier(Base):
    __tablename__ = "modifiers"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, index=True, nullable=False)
    group_id = Column(Integer, ForeignKey("modifier_groups.id"), index=True, nullable=False)
    name = Column(String, nullable=False)
    price_cents = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
