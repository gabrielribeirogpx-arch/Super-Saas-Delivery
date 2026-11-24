from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from app.core.database import Base


class ManagementPushDevice(Base):
    __tablename__ = "management_push_devices"

    token = Column(String(512), primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    admin_user_id = Column(Integer, ForeignKey("admin_users.id", ondelete="CASCADE"), nullable=False)
    credential_version = Column(Integer, nullable=False)
    binding = Column(String(36), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
