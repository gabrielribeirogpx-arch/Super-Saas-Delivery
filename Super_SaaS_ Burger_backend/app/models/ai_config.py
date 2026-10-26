from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text, func

from app.core.database import Base


class AIConfig(Base):
    __tablename__ = "ai_configs"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, index=True, nullable=False, unique=True)
    provider = Column(String, nullable=False, default="mock")
    enabled = Column(Boolean, nullable=False, default=False)
    model = Column(String, nullable=True)
    temperature = Column(Float, nullable=True)
    system_prompt = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
