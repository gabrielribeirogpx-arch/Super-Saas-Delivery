from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, func

from app.core.database import Base


class ModifierGroup(Base):
    __tablename__ = "modifier_groups"
    __table_args__ = (Index("ix_modifier_groups_tenant", "tenant_id"),)

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, index=True, nullable=False)
    name = Column(String, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
