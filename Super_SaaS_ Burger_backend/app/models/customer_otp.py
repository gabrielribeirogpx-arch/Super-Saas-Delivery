from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from app.core.database import Base

class CustomerOtp(Base):
    __tablename__ = "customer_otps"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    phone_normalized = Column(String(32), nullable=False, index=True)
    code_hash = Column(String(128), nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
