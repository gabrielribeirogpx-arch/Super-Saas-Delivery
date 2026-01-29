from sqlalchemy import Column, DateTime, Index, Integer, String, Text, func

from app.core.database import Base


class WhatsAppMessageLog(Base):
    __tablename__ = "whatsapp_message_log"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, nullable=False, index=True)
    direction = Column(String, nullable=False)
    to_phone = Column(String, nullable=True)
    from_phone = Column(String, nullable=True)
    template_name = Column(String, nullable=True)
    message_type = Column(String, nullable=False)
    payload_json = Column(Text, nullable=True)
    status = Column(String, nullable=False)
    error = Column(Text, nullable=True)
    provider_message_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


Index("ix_whatsapp_message_log_tenant_created", WhatsAppMessageLog.tenant_id, WhatsAppMessageLog.created_at)
Index("ix_whatsapp_message_log_to_phone", WhatsAppMessageLog.to_phone)
