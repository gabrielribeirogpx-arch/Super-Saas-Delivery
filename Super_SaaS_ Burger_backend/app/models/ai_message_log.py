from sqlalchemy import Column, DateTime, Integer, String, Text, func

from app.core.database import Base


class AIMessageLog(Base):
    __tablename__ = "ai_message_logs"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, index=True, nullable=False)
    phone = Column(String, index=True, nullable=True)
    direction = Column(String, nullable=False)  # in / out
    provider = Column(String, nullable=False)
    prompt = Column(Text, nullable=True)
    raw_response = Column(Text, nullable=True)
    parsed_json = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
