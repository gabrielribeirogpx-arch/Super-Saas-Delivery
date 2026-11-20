from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func

from app.core.database import Base


class CustomerEmailAccount(Base):
    __tablename__ = "customer_email_accounts"
    __table_args__ = (UniqueConstraint("tenant_id", "email_normalized", name="uq_customer_email_account_tenant_email"),)

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    email_normalized = Column(String(254), nullable=False)
    name = Column(String(120), nullable=False)
    phone_normalized = Column(String(32), nullable=False)
    verified_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
