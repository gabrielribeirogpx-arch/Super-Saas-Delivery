from sqlalchemy import Boolean, Column, DateTime, Integer, String, func

from app.core.database import Base


class WhatsAppConfig(Base):
    __tablename__ = "whatsapp_config"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, index=True, nullable=False)
    provider = Column(String, nullable=False, default="mock")
    phone_number_id = Column(String, nullable=True)
    waba_id = Column(String, nullable=True)
    access_token = Column(String, nullable=True)
    verify_token = Column(String, nullable=True)
    webhook_secret = Column(String, nullable=True)
    is_enabled = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
