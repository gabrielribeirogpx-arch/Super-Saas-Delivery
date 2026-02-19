from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func

from app.core.database import Base


class StoreTheme(Base):
    __tablename__ = "store_themes"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, unique=True, index=True)
    primary_color = Column(String(32), nullable=True)
    secondary_color = Column(String(32), nullable=True)
    logo_url = Column(Text, nullable=True)
    cover_url = Column(Text, nullable=True)
    slogan = Column(String(255), nullable=True)
    show_logo_on_cover = Column(Boolean, nullable=False, default=True, server_default="1")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
