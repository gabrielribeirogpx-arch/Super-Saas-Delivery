from sqlalchemy import Column, Integer, String, Text, DateTime, func

from app.core.database import Base


class WhatsAppOutboundLog(Base):
    __tablename__ = "whatsapp_outbound_log"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, index=True, nullable=False)
    order_id = Column(Integer, index=True, nullable=True)
    phone = Column(String, index=True, nullable=False)
    template = Column(String, nullable=False)
    status = Column(String, nullable=False)
    variables_json = Column(Text, nullable=True)
    response_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
